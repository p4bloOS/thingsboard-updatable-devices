import logging
from deflate import DeflateIO, GZIP
from tarfile import TarFile, DIRTYPE
from json import loads as json_loads
from gc import collect as gc_collect
from os import remove as os_remove, listdir as os_listdir, rmdir as os_rmdir, mkdir as os_mkdir

log = logging.getLogger("ota_installer")
METADATA_FILE_NAME = "FW_METADATA.json"
EXPECTED_METADATA_SUFFIX = ".metadata.json" # Sufijo para el archivo de metadatos asociado al paquete OTA


class OTAInstaller():
    """
    Clase manejadora de la instalación de un paquete OTA recibido, con métodos para comprobar
    el correcto formato del archivo, su coherencia con los datos reportados por la plataforma
    y su instalación sobre el sistema de ficheros con diferentes parámetros de personalización.
    Está pensada para ser usada en la rutina de inicio del dispositivo, tras comprobar que existe
    un nuevo paquete OTA listo para instalarse.
    """

    def __init__(self, ota_package_path: str, quiet=False):
        """
        Contruye un objeto de tipo OTAInstaller.
        Parámetros:
            ota_package_path: ruta del paquete de OTA que se pretende instalar
            quiet: si es True, no se emitará ningún mensaje de log
        """
        self.ota_package_path = ota_package_path
        self.quiet = quiet


    def __log_if_not_quiet(self, message):
        if not self.quiet:
            log.debug(message)


    def check_tar_gz_format(self):
        """
        Comprueba que el paquete OTA es un fichero con el formato TAR.GZ, lanzando
        una excepción en caso negativo.
        """
        with open(self.ota_package_path, 'rb') as ota_file:
            decompressed_file = DeflateIO(ota_file, GZIP)
            tar_file = TarFile(fileobj=decompressed_file)
            try:
                # Esto dará error si el archivo no sigue el formato tar gz
                tar_file.next()
            except Exception as e :
                raise RuntimeError("No se puede leer el paquete OTA como un archivo en"
                " formato .tar.gz") from e


    @staticmethod
    def __read_fw_metadata_json(json_file) -> dict:
        """
        Retorna un diccionario a partir de un archivo JSON.
        Lanza una excepción si el archivo no se puede leer como JSON o si no contiene
        los atributos "title" y "version".
        """
        try:
            fw_metadata = json_loads(json_file.read())
        except ValueError as e:
            raise ValueError("Error mientras se cargaba el fichero JSON de metadatos") from e
        if ( 'title' not in fw_metadata or 'version' not in fw_metadata):
            raise KeyError("No se han encontrado los atributos esperados en FW_METADATA.json "
                "(\"title\" y \"version\")")
        return fw_metadata


    def check_metadata_in_package(self):
        """
        Inspecciona como un TAR.GZ el fichero de OTA y comprueba que contenga dentro el
        fichero FW_METADATA.json.
        Los campos "title" y "version" de FW_METADATA.json deberán coincidir con los reportados
        con la plataforma antes del reincio, almacenados un fichero "<ota_file_name>.metadata.json".
        Lanza una excepción si no se superan las comprobaciones.
        """

        metadata_inside_ota_file = None
        with open(self.ota_package_path, 'rb') as ota_file:
            decompressed_file = DeflateIO(ota_file, GZIP)
            tar_file = TarFile(fileobj=decompressed_file)
            for file_entry in tar_file:
                if file_entry.name == METADATA_FILE_NAME:
                    metadata_file = tar_file.extractfile(file_entry)
                    metadata_inside_ota_file = self.__read_fw_metadata_json(metadata_file)
                    break
        if metadata_inside_ota_file == None:
            raise ValueError(f"'{METADATA_FILE_NAME} no encontrado en el paquete OTA.'")

        with open(
            self.ota_package_path + EXPECTED_METADATA_SUFFIX, 'rb'
        ) as expected_metadata_file:
            expected_metadata = self.__read_fw_metadata_json(expected_metadata_file)

        if metadata_inside_ota_file != expected_metadata:
            raise ValueError("Título y versión de firmware del paquete recibido no coinciden con los "
                "reportados por la plataforma")


    def delete_ota_package(self):
        """
        Elimina el paquete OTA y su fichero de metadatos asociado.
        """
        os_remove(self.ota_package_path)
        os_remove(self.ota_package_path + EXPECTED_METADATA_SUFFIX)


    def __recursive_delete(self, path: str, excluded_paths: list):
        """
        Elimina recursivamente todos los ficheros excepto los indicados.
        """

        path = path[:-1] if path.endswith('/') else path
        if path in excluded_paths:
            self.__log_if_not_quiet(f"Omitiendo borrado de {path}")
            return

        try:
            children = os_listdir(path)
            # no exception thrown, this is a directory
            for child in children:
                self.__recursive_delete(path + '/' + child, excluded_paths)
        except OSError:
            self.__log_if_not_quiet(f"Borrando archivo {path}")
            os_remove(path)
            return

        if path == "" :
            return

        try:
            self.__log_if_not_quiet(f"Borrando directorio {path}")
            os_rmdir(path)
        except OSError as e:
            if e.errno == 39:
                self.__log_if_not_quiet(f"Directorio {path} no vacío. Hay un archivo excluido dentro")
            else:
                raise e


    def install_firmware(self, excluded_files: list, cleanup: bool):
        """
        Aplica el paquete OTA sobreescribiendo el sistema de ficheros.
        Parámetros:
            excluded_files: lista de rutas excluidas (no se modificarán ni borrarán en ningún caso)
            cleanup: si es True, se realizará un borrado de todos los archivos (menos los excluidos)
                     antes de instalar los nuevos archivos.
        """
        gc_collect()

        if cleanup:
            excluded_paths = [
                f"/{path[:-1]}"  if path.endswith("/") else f"/{path}" for path in excluded_files
            ] + [
                f"/{self.ota_package_path}",
                f"/{self.ota_package_path}{EXPECTED_METADATA_SUFFIX}"
            ]
            self.__log_if_not_quiet("Realizando limpieza recursiva")
            self.__recursive_delete("/", excluded_paths)

        self.__log_if_not_quiet("Aplicando paquete OTA sobre el sistema de ficheros")
        with open(self.ota_package_path, 'rb') as ota_file:
            decompressed_file = DeflateIO(ota_file, GZIP)
            tar_file = TarFile(fileobj=decompressed_file)
            for file_entry in tar_file:
                file_name = file_entry.name
                if file_name in excluded_files:
                    item_type = 'directorio' if file_name.endswith('/') else 'fichero'
                    self.__log_if_not_quiet(f'Omitiendo escritura de {item_type} excluido "{file_name}"')
                    continue
                if file_entry.type == DIRTYPE:
                    try:
                        self.__log_if_not_quiet(f"Creando directorio {file_name}")
                        os_mkdir(file_entry.name[:-1])
                    except OSError as e:
                        if e.errno == 17:
                            self.__log_if_not_quiet('El directorio ya existe')
                        else:
                            raise e
                else:
                    self.__log_if_not_quiet(f"Escribiendo archivo {file_name}")
                    file = tar_file.extractfile(file_entry)
                    with open(file_name, "wb") as of:
                        of.write(file.read())
