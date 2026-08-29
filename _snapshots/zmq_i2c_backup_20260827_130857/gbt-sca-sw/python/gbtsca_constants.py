CTRL = {
    # Channels
    "CHANNEL_CTRL": 0x00,
    "CHANNEL_ID": 0x14,
    "CHANNEL_SEC": 0x13,

    # commands
    "W_CRB": 0x2,
    "W_CRC": 0x4,
    "W_CRD": 0x6,

    "R_CRB": 0x3,
    "R_CRC": 0x5,
    "R_CRD": 0x7,

    "R_SEU": 0xf1,
    "SEU_RESET": 0xf0,

    "R_CHIP_ID_V1": 0xd1,
    "R_CHIP_ID_V2": 0x91,

    "MASK_CRB_SPI": 0x02,
    "MASK_CRB_PARAL": 0x04,
    "MASK_CRB_I2C0": 0x08,
    "MASK_CRB_I2C1": 0x10,
    "MASK_CRB_I2C2": 0x20,
    "MASK_CRB_I2C3": 0x40,
    "MASK_CRB_I2C4": 0x80,

    "MASK_CRC_I2C5": 0x01,
    "MASK_CRC_I2C6": 0x02,
    "MASK_CRC_I2C7": 0x04,
    "MASK_CRC_I2C8": 0x08,
    "MASK_CRC_I2C9": 0x10,
    "MASK_CRC_I2C10": 0x20,
    "MASK_CRC_I2C11": 0x40,
    "MASK_CRC_I2C12": 0x80,

    "MASK_CRD_I2C13": 0x01,
    "MASK_CRD_I2C14": 0x02,
    "MASK_CRD_I2C15": 0x04,
    "MASK_CRD_JTAG": 0x08,
    "MASK_CRD_ADC": 0x10,
    "MASK_CRD_DAC": 0x20
}


ADC = {
    "CHANNEL": 0x14,
    "GO_REG": 0x02,
    "W_MUX_REG": 0x50,
    "R_MUX_REG": 0x51
}


I2C = {
    # I2C occupies 16 channels from 0x3 to 0x12
    "CHANNEL_MAP": [0x3, 0x4, 0x5, 0x6, 0x7, 0x8, 0x9,
                    0xa, 0xb, 0xc, 0xd, 0xe, 0xf, 0x10, 0x11, 0x12],

    # commands
    "W_CTRL_REG": 0x30,
    "R_CTRL_REG": 0x31,
    "R_STATUS_REG": 0x11,
    "W_MASK": 0x20,
    "R_MASK": 0x21,
    "W_DATA_0": 0x40,
    "R_DATA_0": 0x41,
    "W_DATA_1": 0x50,
    "R_DATA_1": 0x51,
    "W_DATA_2": 0x60,
    "R_DATA_2": 0x61,
    "W_DATA_3": 0x70,
    "R_DATA_3": 0x71,
    "W_7B_SINGLE": 0x82,
    "R_7B_SINGLE": 0x86,
    "W_7B_MULTI": 0xDA,
    "R_7B_MULTI": 0xDE,
    "W_10B_SINGLE": 0x82,
    "R_10B_SINGLE": 0x86,
    "W_10B_MULTI": 0xDA,
    "R_10B_MULTI": 0xDE,

    # bit masks
    "MASK_CTRL_REG_SCLDRIVE": 0x80,
    "MASK_CTRL_REG_NBYTE": 0x7c,
    "MASK_CTRL_REG_SPEED": 0x03
}


DAC = {
    "CHANNEL": 0x15,
    "W_A": 0x10,
    "R_A": 0x11,
    "W_B": 0x20,
    "R_B": 0x21,
    "W_C": 0x30,
    "R_C": 0x31,
    "W_D": 0x40,
    "R_D": 0x41
}


GPIO = {
    "CHANNEL": 0x02,

    "W_DATAOUT": 0x10,
    "R_DATAOUT": 0x11,
    "R_DATAIN": 0x01,
    "W_DIRECTION": 0x20,
    "R_DIRECTION": 0x21,
    "W_INT_ENABLE": 0x60,
    "R_INT_ENABLE": 0x61,
    "W_INT_SEL": 0x30,
    "R_INT_SEL": 0x31,
    "W_INT_TRIG": 0x40,
    "R_INT_TRIG": 0x41,
    "W_INTS": 0x70,
    "R_INTS": 0x71,
    "W_CLKSEL": 0x80,
    "R_CLKSEL": 0x81,
    "W_EDGESEL": 0x90,
    "R_EDGESEL": 0x91
}
