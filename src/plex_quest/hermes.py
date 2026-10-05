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
        24576: (0x788E35, 116),  # Native seek-hold clearing / opcode anchor.
        24578: (0x788F0E, 159),  # Balanced relative seek and step indicator.
        24581: (0x788FDB, 2990),  # Player KeyBehaviour.onKey generator.
        57908: (0xC08CD1, 147),  # SeekbarView's TV/responsive component selector.
        57910: (0xC08E2C, 947),  # Pointer gesture wrapper around SharedSeekbarView.
        58007: (0xC0DE59, 431),  # Seekbar callback: commit pointer seeks without TV preview-pause.
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
    replacement = bytes([jump_opcode, 4, jump_opcode, 2])
    current = bytes(data[seek_offset + 0x5E4 : seek_offset + 0x5E8])
    if current != replacement:
        ins = seek[0x5E4]
        original_guard = (ins.inst.name, ins.arg1, ins.arg2, ins.arg3) == (
            "JStrictNotEqual", 34, 11, 12)
        earlier_patch = current == bytes([jump_opcode, 34, jump_opcode, 2])
        if not original_guard and not earlier_patch:
            raise UnsupportedBundle("Unexpected seek wake-up guard.")
        # doSeek() already wakes the controls. Skip the redundant await, which
        # otherwise lets key-up overtake held-seek timer registration. The
        # reclaimed block below captures the event's hold-based seek distance.
        data[seek_offset + 0x5E4 : seek_offset + 0x5E8] = replacement

    if functions[24576][0x2C].inst.name != "PutById":
        raise UnsupportedBundle("Unexpected seek-hold field opcode.")
    get_id = data[seek_offset + 0x24]
    put_id = data[expected[24576][0] + 0x2C]
    load_env = data[seek_offset + 0x606]
    event_step = (
        bytes([load_env, 14, 2, 0])
        + bytes([get_id, 12, 4, 34]) + (49673).to_bytes(2, "little")
        + bytes([put_id, 14, 12, 1]) + (49673).to_bytes(2, "little")
        + bytes([jump_opcode, 14])
        + bytes(12)
    )
    data[seek_offset + 0x5E8:seek_offset + 0x606] = event_step

    delta_offset = expected[24578][0]
    delta = functions[24578]
    if delta[0x36].inst.name != "GetById" or seek[0x702].inst.name != "Sub":
        raise UnsupportedBundle("Unexpected relative seek opcode anchors.")
    load_int = data[seek_offset + 0x10F]
    load_zero = data[expected[57910][0] + 0x41]
    move = data[expected[57910][0] + 0x2B5]
    jump_false = data[expected[59030][0] + 0xA4]
    # One per-event distance feeds both directions. Original sign, player.seek(),
    # range enforcement, pause state, and step indicators remain in that callback.
    # An absent native field defaults to 10 seconds for normal media-key events.
    delta_code = (
        bytes([load_int, 4]) + (10000).to_bytes(4, "little", signed=True)
        + bytes([get_id, 2, 2, 3]) + (49673).to_bytes(2, "little")
        + bytes([jump_false, 6, 2, move, 4, 2])
        + bytes([jump_false, 9, 3, load_zero, 5])
        + bytes([data[seek_offset + 0x702], 4, 5, 4])
        + bytes([jump_opcode, 4]) + bytes(2)
    )
    current_delta = bytes(data[delta_offset + 0xE:delta_offset + 0x2D])
    if current_delta != delta_code:
        if (delta[0x1C].inst.name, delta[0x1C].arg1, delta[0x1C].arg2,
                delta[0x24].inst.name, delta[0x24].arg1) != ("GetById", 4, 2, "GetById", 2):
            raise UnsupportedBundle("Unexpected relative seek distance calculation.")
    data[delta_offset + 0xE:delta_offset + 0x2D] = delta_code

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

    selector_offset = expected[57908][0]
    selector = functions[57908]
    ins = selector[0x74]
    if (ins.inst.name, ins.arg1, ins.arg2) not in (
        ("GetByIdShort", 4, 3), ("GetByIdShort", 4, 1)
    ):
        raise UnsupportedBundle("Unexpected TV seekbar component selector.")
    # Both selector slots use the existing pointer-aware wrapper. Its inner
    # SharedSeekbarView still uses the TV layout, focus, and keyboard controls.
    data[selector_offset + 0x76] = 1

    pointer_offset = expected[57910][0]
    pointer = functions[57910]
    string_ins = selector[0x7E]
    if (string_ins.inst.name, string_ins.arg2) != ("LoadConstStringLongIndex", 84136):
        raise UnsupportedBundle("Unexpected seekbar marker string.")
    # Build the same native wrapper with testID="SeekbarView", using its existing
    # string-table entry. The marker lets native input distinguish timeline
    # gestures from transport-button and video-background clicks. Rebuild only
    # this inexpensive wrapper instead of its compiler-generated JSX memo block.
    marker = bytearray(data[selector_offset + 0x7E:selector_offset + 0x84])
    marker[1] = 18
    opcode_positions = {
        "LoadFromEnvironment": 0x2D7,
        "GetByIdShort": 0x1B,
        "NewObject": 0xD4,
        "PutNewOwnByIdShort": 0x2EB,
        "PutNewOwnById": 0x2EF,
        "Call3": 0x2F4,
        "Call2": 0x16,
        "Mov": 0x2B5,
        "PutByVal": 0x2B1,
    }
    opcodes = {}
    for name, position in opcode_positions.items():
        if pointer[position].inst.name != name:
            raise UnsupportedBundle(f"Unexpected seekbar opcode anchor: {name}.")
        opcodes[name] = data[pointer_offset + position]
    get_value = data[pointer_offset + 0x10]
    # A trigger tap must activate the pointer gesture immediately, rather than
    # falling through to the focusable TV timeline's select/play-pause action.
    activate_tap = (
        bytes([marker[0], 18]) + (101).to_bytes(4, "little")  # gesture.config.
        + bytes([get_value, 18, 6, 18])
        + bytes([marker[0], 7]) + (63009).to_bytes(4, "little")  # minDist.
        + bytes([load_zero, 17])
        + bytes([opcodes["PutByVal"], 18, 7, 17])
    )
    replacement = (
        bytes([opcodes["LoadFromEnvironment"], 0, 1, 4])
        + bytes([opcodes["GetByIdShort"], 15, 0, 23, 174])  # JSX runtime.
        + bytes([opcodes["LoadFromEnvironment"], 0, 1, 2])
        + bytes([opcodes["GetByIdShort"], 14, 0, 25, 50])  # Native View.
        + bytes([opcodes["NewObject"], 0])
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 16, 231])  # style.
        + bytes([opcodes["PutNewOwnById"], 0, 12]) + (53239).to_bytes(2, "little")  # onLayout.
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 9, 95])  # children.
        + activate_tap
        + bytes(marker)
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 18, 237])  # testID.
        + bytes([opcodes["Call3"], 0, 15, 10, 14, 0])
        + bytes([opcodes["Mov"], 4, 0])
    )
    window_start, window_end = 0x30F, 0x35B
    window_size = window_end - window_start
    replacement += bytes([jump_opcode, window_size - len(replacement)])
    replacement += bytes(window_size - len(replacement))  # Unreachable padding.
    current = bytes(data[pointer_offset + window_start:pointer_offset + window_end])
    if current != replacement:
        if (pointer[window_start].inst.name, pointer[window_start].arg1,
                pointer[window_start].arg2) != ("GetByVal", 0, 3):
            raise UnsupportedBundle("Unexpected seekbar JSX memo layout.")
        if (pointer[0x337].inst.name, pointer[0x337].arg1) != ("NewObject", 0):
            raise UnsupportedBundle("Unexpected seekbar wrapper props.")
        if (pointer[0x342].inst.name, pointer[0x342].arg1, pointer[0x342].arg2) != (
            "PutNewOwnByIdShort", 0, 9
        ):
            raise UnsupportedBundle("Unexpected seekbar wrapper child.")
        if (pointer[0x346].inst.name, pointer[0x346].arg1) != ("Call3", 0):
            raise UnsupportedBundle("Unexpected seekbar wrapper renderer.")
    data[pointer_offset + window_start:pointer_offset + window_end] = replacement

    # TV screens do not mount a GestureHandlerRootView. The detector must be
    # inside a native gesture root, otherwise its pan/tap callbacks never run.
    # Reuse the gesture module already imported by this wrapper and put a root
    # around the detector, with forceActive for TV-focusable native children.
    load_true = data[seek_offset + 0x7A]
    root_code = (
        bytes([opcodes["LoadFromEnvironment"], 8, 1, 4])
        + bytes([opcodes["GetByIdShort"], 9, 8, 23, 174])
        + bytes([opcodes["LoadFromEnvironment"], 8, 1, 0])
        + bytes([opcodes["LoadFromEnvironment"], 7, 1, 1])
        + bytes([get_value, 7, 7, 2])
        + bytes([opcodes["Call2"], 7, 8, 10, 7])  # require(gesture module).
        + bytes([get_id, 8, 7, 26]) + (24951).to_bytes(2, "little")  # GestureDetector.
        + bytes([opcodes["NewObject"], 0])
        + bytes([opcodes["PutNewOwnById"], 0, 6]) + (24955).to_bytes(2, "little")
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 4, 95])
        + bytes([opcodes["Call3"], 4, 9, 10, 8, 0])
        + bytes([marker[0], 8]) + (34614).to_bytes(4, "little")  # GestureHandlerRootView.
        + bytes([get_value, 8, 7, 8])  # Computed property: no new inline-cache slot.
        + bytes([opcodes["NewObject"], 0])
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 16, 231])
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 4, 95])
        + bytes([load_true, 7])
        + bytes([opcodes["PutNewOwnById"], 0, 7]) + (64756).to_bytes(2, "little")
        + bytes([opcodes["Call3"], 0, 9, 10, 8, 0])
    )
    root_start, root_end = 0x35B, 0x3B1
    root_size = root_end - root_start
    root_code += bytes([jump_opcode, root_size - len(root_code)])
    root_code += bytes(root_size - len(root_code))
    current_root = bytes(data[pointer_offset + root_start:pointer_offset + root_end])
    if current_root != root_code:
        original_root = pointer.get(root_start)
        if original_root is None or (original_root.inst.name, original_root.arg1,
                                     original_root.arg2) != ("GetByVal", 0, 3):
            raise UnsupportedBundle("Unexpected seekbar gesture-detector memo layout.")
    data[pointer_offset + root_start:pointer_offset + root_end] = root_code

    commit_offset = expected[58007][0]
    commit = functions[58007]
    if (commit[0x11E].inst.name, commit[0x11E].arg1) != ("LoadConstFalse", 5):
        raise UnsupportedBundle("Unexpected committed seek mode.")
    commit_code = bytes([data[commit_offset + 0x11E], 0, jump_opcode, 7]) + bytes(5)
    current_commit = bytes(data[commit_offset + 0xE:commit_offset + 0x17])
    if current_commit != commit_code:
        if (commit[0xE].inst.name, commit[0xE].arg1, commit[0xE].arg2,
                commit[0x11].inst.name, commit[0x11].arg1) != ("LoadParam", 0, 2, "JmpTrueLong", 311):
            raise UnsupportedBundle("Unexpected seekbar preview-mode branch.")
    # Commit at the pointer location without entering seekPanTo() or the TV
    # ScrubbingSeekInterceptor, both of which pause running playback for preview.
    # The original permission checks, seek-window clamps, and player.seek(false)
    # path preserve the user's existing playing/paused state.
    data[commit_offset + 0xE:commit_offset + 0x17] = commit_code

    data[-20:] = sha1(data[:-20]).digest()
    patched = bytes(data)
    verifier = HBCReader()
    verifier.read_whole_file(BytesIO(patched))  # Includes the Hermes footer check.
    for number in expected:
        list(parse_hbc_bytecode(verifier.function_headers[number], verifier))
    return patched
