from loguru import logger
import time
from typing import Tuple, Optional, Union, List
import asyncio
from dataclasses import dataclass

@dataclass # Convenience! Auto generates init, repr, etc for us. So clean
class ChipInfo:
    """Store detected chip information"""
    manufacturer_id: int
    device_id: int
    size_mb: int
    page_size: int
    sector_size: int
    
    def __str__(self) -> str:
         # The __str__ method to provide readable chip info
        return (f"Flash Chip: Manufacturer ID: 0x{self.manufacturer_id:02X}, "
                f"Device ID: 0x{self.device_id:04X}, Size: {self.size_mb}MB")
    

    class SPIController:
        """
    Advanced SPI Flash Controller
    Handles high speed communication with SPI flash chips via CH341A programmer.
    
    Features:
    Automatic chip detection and configuration
    High speed read operations with integrity checks
    Intelligent error handling and recovery
    Real time progress monitoring
        """
    
    # SPI Flash Commands (Standard JEDEC)
    CMD_WRITE_ENABLE = 0x06
    CMD_WRITE_DISABLE = 0x04
    CMD_READ_ID = 0x9F
    CMD_READ_STATUS = 0x05
    CMD_WRITE_STATUS = 0x01
    CMD_READ_DATA = 0x03
    CMD_FAST_READ = 0x0B
    CMD_PAGE_PROGRAM = 0x02
    CMD_SECTOR_ERASE = 0x20
    CMD_CHIP_ERASE = 0xC7
    
    # Status Register Bits
    STATUS_WIP = 0x01  # Write In Progress
    STATUS_WEL = 0x02  # Write Enable Latch


    def __init__(self, bus: int = 0, device: int = 0):
        """Initialize the SPI controller with advanced error checking"""
         # Assign bus and device to SPI controller
        self.bus = bus
        self.device = device
        self.spi = None # Placeholder for the SPI device interface
        self.chip_info = None # Placeholder for detected chip info once connected
        self._is_connected = False # Track connection status to avoid blind operations
        self._buffer_size = 4096  #Buffer size: selected for speed vs memory balance for nowww
        logger.info(f"Initializing SPI Controller on bus {bus}, device {device}")


    def _verify_connection(self) -> None:
        """Verify SPI connection is active"""
        if not self._is_connected or not self.spi:
            raise ConnectionError("SPI device not connected. Call connect() first.")

    async def connect(self) -> bool:
        """
        Establish connection to SPI device with advanced setup
        Returns: bool indicating success
        """
        try:
            import spidev # Local import only load this if actually trying to connect
            self.spi = spidev.SpiDev()
            self.spi.open(self.bus, self.device)
            
            # Optimize SPI settings for maximum reliability
            self.spi.max_speed_hz = 10000000  # 10MHz - Will auto-negotiate down if needed
            self.spi.mode = 0 # SPI mode 0 (CPOL=0, CPHA=0)
            self.spi.bits_per_word = 8
            self.spi.lsbfirst = False
            
            # Verify connection with test command
            if self._test_connection():
                self._is_connected = True
                logger.success("SPI connection established successfully")
                
                # Auto detect connected chip
                self.chip_info = self._detect_chip()
                if self.chip_info:
                    logger.info(f"Detected: {self.chip_info}")
                return True
            
            # If test fails, log it and return failure
            logger.error("SPI connection test failed")
            return False
            
        except Exception as e:
            # badddd
            logger.error(f"Failed to initialize SPI: {str(e)}")
            return False

    def _test_connection(self) -> bool:
        """Verify SPI communication with test commands"""
        try:
            # Read JEDEC ID as connection test
            self.spi.xfer([self.CMD_READ_ID])
            response = self.spi.readbytes(3) # Should be exactly 3 bytes
            return len(response) == 3 
        except Exception:
            # baddd
            return False

    def _detect_chip(self) -> Optional[ChipInfo]:
        """
        Detect and identify connected flash chip
        Returns ChipInfo object or None if detection fails
        """
        try:
            # Send JEDEC ID command
            self.spi.xfer([self.CMD_READ_ID])
            response = self.spi.readbytes(3)
            
            manufacturer_id = response[0]
            device_id = (response[1] << 8) | response[2]
            
            # Lookup chip details (will expandd)
            chip_sizes = {
                0xEF4016: (2, 256, 4096),    # W25Q16 (2MB)
                0xEF4017: (4, 256, 4096),    # W25Q32 (4MB)
                0xEF4018: (8, 256, 4096),    # W25Q64 (8MB)
                0xEF4019: (16, 256, 4096),   # W25Q128 (16MB)
            }
            # Unique identifier for each chip.
            chip_id = (manufacturer_id << 16) | device_id
            if chip_id in chip_sizes:
                # Return populated ChipInfo if the chip is recognized.
                size_mb, page_size, sector_size = chip_sizes[chip_id]
                return ChipInfo(manufacturer_id, device_id, size_mb, page_size, sector_size)
                # sorry cannot find
            logger.warning(f"Unknown chip ID: 0x{chip_id:06X}")
            return None
            
        except Exception as e:
            logger.error(f"Chip detection failed: {str(e)}")
            return None

    async def read_firmware(self, start_address: int = 0, length: Optional[int] = None) -> Optional[bytes]:
        """
        Read firmware data with error handling and progress monitoring
        
        Args:
            start_address: Starting address to read from
            length: Number of bytes to read (None = entire chip)
            
        Returns:
            bytes containing the read data or None if failed
        """
        self._verify_connection()
        
        try:
            if not length and self.chip_info:
                length = self.chip_info.size_mb * 1024 * 1024
            elif not length:
                 # No chip size available and no length provided; problem
                raise ValueError("Must specify length if chip size unknown")
                
            data = bytearray() # Buffer for the data we read.
            address = start_address
            remaining = length
            
            # Monitor progress as we read
            with logger.progress("Reading firmware...") as progress:
                while remaining > 0:
                    # Read a chunk of data each time
                    chunk_size = min(remaining, self._buffer_size)
                    chunk = await self._read_chunk(address, chunk_size)
                    if not chunk:
                        raise IOError(f"Failed to read at address 0x{address:06X}")
                        
                    data.extend(chunk)
                    address += chunk_size
                    remaining -= chunk_size
                    
                    # Update progress
                    progress.update(f"Read {len(data)}/{length} bytes")
                    
            logger.success(f"Successfully read {len(data)} bytes of firmware")
            return bytes(data)
            
        except Exception as e:
            # badd see log
            logger.error(f"Firmware read failed: {str(e)}")
            return None

    async def _read_chunk(self, address: int, length: int) -> Optional[bytes]:
        """Read a chunk of data with retries and verification"""
        for attempt in range(3):  # 3 retries
            try:
                # Fast read command with address
                cmd = [
                    self.CMD_FAST_READ,
                    (address >> 16) & 0xFF,
                    (address >> 8) & 0xFF,
                    address & 0xFF,
                    0  # Dummy byte for fast read
                ]
                # Send command and read response
                self.spi.xfer(cmd)
                data = self.spi.readbytes(length)
                 # Ensuring we got the expected amount of data
                if len(data) == length:
                    return bytes(data)
                    
            except Exception as e:
                logger.warning(f"Read attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(0.1)  # Short delay before retry
                
        return None

    def close(self) -> None:
        """Clean up resources and close connection"""
        if self.spi:
            self.spi.close()
            self._is_connected = False
            logger.info("SPI connection closed")

