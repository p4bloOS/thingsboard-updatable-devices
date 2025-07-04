"""
ota_helper.py
Inspirado por el proyecto "uota" de mkomon.
(https://github.com/mkomon/uota/tree/daf71b75950ee325168b9c74ec6540df7bf331dd)
"""

import utils


def recursive_delete(path: str):
    """
    Delete a directory recursively, removing files from all sub-directories before
    finally removing empty directory. Works for both files and directories.

    No limit to the depth of recursion, will fail on too deep dir structures.
    """
    # prevent deleting the whole filesystem and skip non-existent files
    if not path or not uos.stat(path):
        return

    path = path[:-1] if path.endswith('/') else path

    try:
        children = uos.listdir(path)
        # no exception thrown, this is a directory
        for child in children:
            recursive_delete(path + '/' + child)
    except OSError:
        uos.remove(path)
        return
    uos.rmdir(path)


def check_free_space(min_free_space: int) -> bool:
    """
    Check available free space in filesystem and return True/False if there is enough free space
    or not.

    min_free_space is measured in kB
    """
    if not any([isinstance(min_free_space, int), isinstance(min_free_space, float)]):
        log.warning('min_free_space must be an int or float')
        return False

    fs_stat = uos.statvfs('/')
    block_sz = fs_stat[0]
    free_blocks = fs_stat[3]
    free_kb = block_sz * free_blocks / 1024
    return free_kb >= min_free_space


def install_new_firmware(quiet=False):
    """
    Unpack new firmware that is already downloaded and perform a post-installation cleanup.
    """
    gc.collect()

    if not load_ota_cfg():
        return

    try:
        uos.stat(ota_config['tmp_filename'])
    except OSError:
        log.info('No new firmware file found in flash.')
        return

    with open(ota_config['tmp_filename'], 'rb') as f1:
        f2 = deflate.DeflateIO(f1, deflate.GZIP)
        f3 = tarfile.TarFile(fileobj=f2)
        for _file in f3:
            file_name = _file.name
            if file_name in ota_config['excluded_files']:
                item_type = 'directory' if file_name.endswith('/') else 'file'
                not quiet and log.info(f'Skipping excluded {item_type} {file_name}')
                continue

            if file_name.endswith('/'):  # is a directory
                try:
                    not quiet and log.debug(f'creating directory {file_name} ... ')
                    uos.mkdir(file_name[:-1])  # without trailing slash or fail with errno 2
                    not quiet and log.debug('ok')
                except OSError as e:
                    if e.errno == 17:
                        not quiet and log.debug('already exists')
                    else:
                        raise e
                continue
            file_obj = f3.extractfile(_file)
            with open(file_name, 'wb') as f_out:
                written_bytes = 0
                while True:
                    buf = file_obj.read(512)
                    if not buf:
                        break
                    written_bytes += f_out.write(buf)
                not quiet and log.info(f'file {file_name} ({written_bytes} B) written to flash')

    uos.remove(ota_config['tmp_filename'])
    if load_ota_cfg():
        for filename in ota_config['delete']:
            recursive_delete(filename)
