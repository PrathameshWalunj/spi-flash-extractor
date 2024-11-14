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

