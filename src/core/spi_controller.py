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
