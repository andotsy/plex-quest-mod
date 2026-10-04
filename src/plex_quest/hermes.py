from hashlib import sha1
from io import BytesIO

from hermes_dec.parsers.hbc_bytecode_parser import parse_hbc_bytecode
from hermes_dec.parsers.hbc_file_parser import HBCReader


class UnsupportedBundle(ValueError):
    pass


def patch_bundle(original: bytes) -> bytes:
    """Apply fixed-size patches; reject unknown Hermes layouts before writing."""
    reader = HBCReader()
    source = BytesIO(original)
    reader.read_whole_file(source)
    if reader.header.version != 96:
        raise UnsupportedBundle("Expected Hermes bytecode v96 for Plex 2026.17.0.")

    expected = {
        24581: (0x788FDB, 2990),  # Player KeyBehaviour.onKey generator.
        58065: (0xC10E00, 88),  # DeckCloseTarget.onFocus: close deck, wake controls.
        59029: (0xC48D93, 442),  # DetailsRowInternal.
        59030: (0xC48F4D, 388),  # DetailsChildrenRow.
    }
    functions = {}
    for number, layout in expected.items():
        if number >= len(reader.function_headers):
            raise UnsupportedBundle("Missing supported Plex function table.")
        header = reader.function_headers[number]
        if (header.offset, header.bytecodeSizeInBytes) != layout:
            raise UnsupportedBundle(f"Unsupported function layout: #{number}.")
        functions[number] = {
            ins.original_pos: ins for ins in parse_hbc_bytecode(header, reader)
        }

    data = bytearray(original)
    seek_offset = expected[24581][0]
    seek = functions[24581]
    if seek[0x33C].inst.name != "Jmp":
        raise UnsupportedBundle("Unexpected seek branch opcode.")
    jump_opcode = data[seek_offset + 0x33C]
    replacement = bytes([jump_opcode, 34, jump_opcode, 2])
    current = bytes(data[seek_offset + 0x5E4 : seek_offset + 0x5E8])
    if current != replacement:
        ins = seek[0x5E4]
        if (ins.inst.name, ins.arg1, ins.arg2, ins.arg3) != (
            "JStrictNotEqual", 34, 11, 12
        ):
            raise UnsupportedBundle("Unexpected seek wake-up guard.")
        # doSeek() already wakes the controls. Skip the redundant await, which
        # otherwise lets key-up overtake held-seek timer registration.
        data[seek_offset + 0x5E4 : seek_offset + 0x5E8] = replacement

    row_offset = expected[59030][0]
    for position, opcode, distance, old_register in (
        (0xA4, "JmpFalse", 6, 2),
        (0xA7, "JmpTrue", 7, 9),
        (0x144, "JmpFalse", 34, 4),
    ):
        ins = functions[59030][position]
        if ins.inst.name != opcode or ins.arg1 != distance or ins.arg2 not in (old_register, 6):
            raise UnsupportedBundle(f"Unexpected details-row guard at {position:#x}.")
        # Real child/sibling data takes precedence over placeholder/rollout flags.
        data[row_offset + position + 2] = 6

    inner_offset = expected[59029][0]
    inner = functions[59029]
    if inner[0xA2].inst.name != "Jmp":
        raise UnsupportedBundle("Unexpected child-list branch opcode.")
    replacement = bytes([data[inner_offset + 0xA2], 25, 0, 0, 0])
    current = bytes(data[inner_offset + 0x73 : inner_offset + 0x78])
    if current != replacement:
        ins = inner[0x73]
        if (ins.inst.name, ins.arg1, ins.arg2) != ("GetByIdShort", 7, 4):
            raise UnsupportedBundle("Unexpected episode-only row whitelist.")
        # Keep the existing nonempty-content and TV-layout guards, then use the
        # same list renderer for seasons as well as episodes. Padding is the
        # v96 one-byte Unreachable opcode; it is never executed.
    data[inner_offset + 0x73 : inner_offset + 0x78] = replacement

    exit_offset = expected[58065][0]
    replacement = bytes([jump_opcode, 4, jump_opcode, 2])
    current = bytes(data[exit_offset + 0x12 : exit_offset + 0x16])
    if current != replacement:
        ins = functions[58065][0x12]
        if (ins.inst.name, ins.arg1, ins.arg2, ins.arg3) != ("JStrictNotEqual", 66, 1, 0):
            raise UnsupportedBundle("Unexpected deck-exit focus guard.")
        # An explicit upward gesture should return from any deck section. The
        # original callback already closes the deck and wakes the transport UI.
        data[exit_offset + 0x12 : exit_offset + 0x16] = replacement

    data[-20:] = sha1(data[:-20]).digest()
    patched = bytes(data)
    verifier = HBCReader()
    verifier.read_whole_file(BytesIO(patched))  # Includes the Hermes footer check.
    for number in expected:
        list(parse_hbc_bytecode(verifier.function_headers[number], verifier))
    return patched
