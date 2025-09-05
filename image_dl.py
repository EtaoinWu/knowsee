import logging

import aiohttp
from beartype import beartype

# Set up module-level logger
logger = logging.getLogger(__name__)


@beartype
class ImageDownloader:
    def __init__(self, image_urls: dict[str, str]):
        self.session = aiohttp.ClientSession()
        self.image_urls = image_urls

    async def fetch(self, name: str):
        url = self.image_urls.get(name)
        if not url:
            raise ValueError(f"No image URL configured for {name}")
        async with self.session.get(url) as response:
            if response.status != 200:
                raise ConnectionError("Failed to fetch image")
            return await response.read()

    async def close(self):
        await self.session.close()