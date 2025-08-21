

class UpdatableLoraNode():



    async def _manage_OTA_update(self):
        pass

    async def run_OTA_manager(self):
        """
        Itera infinitamente sobre el procedimiento de la OTA.
        """
        while True:
            log.debug("Manejador de OTAs a la escucha")
            await self._manage_OTA_update()
