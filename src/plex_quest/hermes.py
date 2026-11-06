from hashlib import sha1
from io import BytesIO

from hermes_dec.parsers.hbc_bytecode_parser import parse_hbc_bytecode
from hermes_dec.parsers.hbc_file_parser import HBCReader

from .profiles import PROFILES, BuildProfile


class UnsupportedBundle(ValueError):
    pass


def identify_bundle(reader: HBCReader) -> BuildProfile:
    if reader.header.version != 96:
        raise UnsupportedBundle("Expected Hermes bytecode v96 for a supported Plex build.")
    for profile in PROFILES:
        if all(number < len(reader.function_headers)
               and (reader.function_headers[number].offset,
                    reader.function_headers[number].bytecodeSizeInBytes) == (offset, size)
               for number, offset, size in profile.functions.values()):
            return profile
    raise UnsupportedBundle("Unsupported Plex function layout. Supported builds: "
                            + ", ".join(profile.label for profile in PROFILES))


def bundle_profile(original: bytes) -> BuildProfile:
    reader = HBCReader()
    reader.read_whole_file(BytesIO(original))
    return identify_bundle(reader)


def patch_bundle(original: bytes) -> bytes:
    """Apply fixed-size patches; reject unknown Hermes layouts before writing."""
    reader = HBCReader()
    reader.read_whole_file(BytesIO(original))
    profile = identify_bundle(reader)
    expected = profile.functions
    strings = {value: index for index, value in enumerate(reader.strings)}
    def sid(name: str) -> int:
        if name not in strings:
            raise UnsupportedBundle(f"Missing supported Plex string: {name}.")
        return strings[name]

    functions = {}
    for role, (number, offset, size) in expected.items():
        if number >= len(reader.function_headers):
            raise UnsupportedBundle("Missing supported Plex function table.")
        header = reader.function_headers[number]
        if (header.offset, header.bytecodeSizeInBytes) != (offset, size):
            raise UnsupportedBundle(f"Unsupported function layout: #{number}.")
        functions[role] = {
            ins.original_pos: ins for ins in parse_hbc_bytecode(header, reader)
        }

    data = bytearray(original)
    seek_offset = expected["keys"][1]
    seek = functions["keys"]
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

    if functions["clear_seek"][0x2C].inst.name != "PutById":
        raise UnsupportedBundle("Unexpected seek-hold field opcode.")
    get_id = data[seek_offset + 0x24]
    put_id = data[expected["clear_seek"][1] + 0x2C]
    load_env = data[seek_offset + 0x606]
    # Screen-background taps and the assigned controller buttons all arrive as
    # playOrPause. Reuse the seek patch's unreachable padding for a visibility
    # guard, branching on Plex's own isSleeping snapshot rather than a timer or
    # a native-view heuristic. Hidden controls wake without toggling playback;
    # visible controls retain the original play/pause and seek-commit paths.
    for position, operands in {
        0x9C: ("StrictEq", 7, 5, 12),
        0x96: ("GetById", 5, 6, 9, sid("isSleeping")),  # isSleeping.
        0x972: ("LoadFromEnvironment", 10, 5, 0),
        0xAC3: ("LoadFromEnvironment", 6, 2, 0),
        0xAD6: ("GetById", 7, 8, 20, sid("wakeUp")),  # wakeUp.
    }.items():
        ins = seek[position]
        actual = (ins.inst.name, *(getattr(ins, f"arg{n}") for n in range(1, len(operands))))
        if actual != operands:
            raise UnsupportedBundle("Unexpected playback-controls visibility logic.")
    branch = seek[0x3AC]
    if (branch.inst.name, branch.arg1, branch.arg2, branch.arg3) not in (
        ("JStrictEqualLong", 0x972 - 0x3AC, 13, 10),
        ("JStrictEqualLong", 0x5FA - 0x3AC, 13, 10),
    ):
        raise UnsupportedBundle("Unexpected play/pause dispatch branch.")
    if seek[0x57].inst.name != "JmpTrueLong" or seek[0x921].inst.name != "JmpLong":
        raise UnsupportedBundle("Unexpected playback-controls jump opcodes.")
    visibility_guard = (
        bytes([data[seek_offset + 0x57]])
        + (0xAC3 - 0x5FA).to_bytes(4, "little", signed=True) + bytes([7])
        + bytes([data[seek_offset + 0x921]])
        + (0x972 - 0x600).to_bytes(4, "little", signed=True)
        + bytes(1)
    )
    event_step = (
        bytes([load_env, 14, 2, 0])
        + bytes([get_id, 12, 4, 34]) + sid("forwardTimeMs").to_bytes(2, "little")
        + bytes([put_id, 14, 12, 1]) + sid("forwardTimeMs").to_bytes(2, "little")
        + bytes([jump_opcode, 14])
        + visibility_guard
    )
    data[seek_offset + 0x5E8:seek_offset + 0x606] = event_step
    data[seek_offset + 0x3AD:seek_offset + 0x3B1] = (0x5FA - 0x3AC).to_bytes(4, "little", signed=True)

    delta_offset = expected["seek_delta"][1]
    delta = functions["seek_delta"]
    if delta[0x36].inst.name != "GetById" or seek[0x702].inst.name != "Sub":
        raise UnsupportedBundle("Unexpected relative seek opcode anchors.")
    load_int = data[seek_offset + 0x10F]
    load_zero = data[expected["pointer"][1] + profile.pointer_zero]
    move = data[expected["pointer"][1] + 0x2B5 + profile.pointer_shift]
    jump_false = data[expected["details_row"][1] + 0xA4]
    # One per-event distance feeds both directions. Original sign, player.seek(),
    # range enforcement, pause state, and step indicators remain in that callback.
    # An absent native field defaults to 10 seconds for normal media-key events.
    delta_code = (
        bytes([load_int, 4]) + (10000).to_bytes(4, "little", signed=True)
        + bytes([get_id, 2, 2, 3]) + sid("forwardTimeMs").to_bytes(2, "little")
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

    row_offset = expected["details_row"][1]
    for position, opcode, distance, old_register in (
        (0xA4, "JmpFalse", 6, 2),
        (0xA7, "JmpTrue", 7, 9),
        (0x144, "JmpFalse", 34, 4),
    ):
        ins = functions["details_row"][position]
        if ins.inst.name != opcode or ins.arg1 != distance or ins.arg2 not in (old_register, 6):
            raise UnsupportedBundle(f"Unexpected details-row guard at {position:#x}.")
        # Real child/sibling data takes precedence over placeholder/rollout flags.
        data[row_offset + position + 2] = 6

    inner_offset = expected["details_inner"][1]
    inner = functions["details_inner"]
    whitelist, after_whitelist, id_register, items_register, jump_anchor = profile.row_whitelist
    if inner[jump_anchor].inst.name != "Jmp":
        raise UnsupportedBundle("Unexpected child-list branch opcode.")
    replacement = bytes([data[inner_offset + jump_anchor], after_whitelist - whitelist, 0, 0, 0])
    current = bytes(data[inner_offset + whitelist : inner_offset + whitelist + 5])
    if current != replacement:
        ins = inner[whitelist]
        if (ins.inst.name, ins.arg1, ins.arg2) != ("GetByIdShort", id_register, items_register):
            raise UnsupportedBundle("Unexpected episode-only row whitelist.")
        # Keep the existing nonempty-content and TV-layout guards, then use the
        # same list renderer for seasons as well as episodes. Padding is the
        # v96 one-byte Unreachable opcode; it is never executed.
    data[inner_offset + whitelist : inner_offset + whitelist + 5] = replacement

    exit_offset = expected["deck_exit"][1]
    replacement = bytes([jump_opcode, 4, jump_opcode, 2])
    current = bytes(data[exit_offset + 0x12 : exit_offset + 0x16])
    if current != replacement:
        ins = functions["deck_exit"][0x12]
        if (ins.inst.name, ins.arg1, ins.arg2, ins.arg3) != ("JStrictNotEqual", 66, 1, 0):
            raise UnsupportedBundle("Unexpected deck-exit focus guard.")
        # An explicit upward gesture should return from any deck section. The
        # original callback already closes the deck and wakes the transport UI.
    data[exit_offset + 0x12 : exit_offset + 0x16] = replacement

    selector_offset = expected["selector"][1]
    selector = functions["selector"]
    ins = selector[0x74]
    if (ins.inst.name, ins.arg1, ins.arg2) not in (
        ("GetByIdShort", 4, 3), ("GetByIdShort", 4, 1)
    ):
        raise UnsupportedBundle("Unexpected TV seekbar component selector.")
    # Both selector slots use the existing pointer-aware wrapper. Its inner
    # SharedSeekbarView still uses the TV layout, focus, and keyboard controls.
    data[selector_offset + 0x76] = 1

    pointer_offset = expected["pointer"][1]
    pointer = functions["pointer"]
    string_ins = selector[0x7E]
    if (string_ins.inst.name, string_ins.arg2) != ("LoadConstStringLongIndex", sid("SeekbarView")):
        raise UnsupportedBundle("Unexpected seekbar marker string.")
    # Build the same native wrapper with testID="SeekbarView", using its existing
    # string-table entry. The marker lets native input distinguish timeline
    # gestures from transport-button and video-background clicks. Rebuild only
    # this inexpensive wrapper instead of its compiler-generated JSX memo block.
    marker = bytearray(data[selector_offset + 0x7E:selector_offset + 0x84])
    marker[1] = 18
    opcode_positions = {
        "LoadFromEnvironment": 0x2D7 + profile.pointer_shift,
        "GetByIdShort": 0x1B,
        "NewObject": profile.pointer_object,
        "PutNewOwnByIdShort": 0x2EB + profile.pointer_shift,
        "PutNewOwnById": 0x2EF + profile.pointer_shift,
        "Call3": 0x2F4 + profile.pointer_shift,
        "Call2": 0x16,
        "Mov": 0x2B5 + profile.pointer_shift,
        "PutByVal": 0x2B1 + profile.pointer_shift,
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
        bytes([marker[0], 18]) + sid("config").to_bytes(4, "little")  # gesture.config.
        + bytes([get_value, 18, 6, 18])
        + bytes([marker[0], 7]) + sid("minDist").to_bytes(4, "little")  # minDist.
        + bytes([load_zero, 17])
        + bytes([opcodes["PutByVal"], 18, 7, 17])
    )
    replacement = (
        bytes([opcodes["LoadFromEnvironment"], 0, 1, 4])
        + bytes([opcodes["GetByIdShort"], 15, 0, 23, sid("jsx")])  # JSX runtime.
        + bytes([opcodes["LoadFromEnvironment"], 0, 1, 2])
        + bytes([opcodes["GetByIdShort"], 14, 0, 25, sid("View")])  # Native View.
        + bytes([opcodes["NewObject"], 0])
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 16, sid("style")])  # style.
        + bytes([opcodes["PutNewOwnById"], 0, 12]) + sid("onLayout").to_bytes(2, "little")  # onLayout.
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 9, sid("children")])  # children.
        + activate_tap
        + bytes(marker)
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 18, sid("testID")])  # testID.
        + bytes([opcodes["Call3"], 0, 15, 10, 14, 0])
        + bytes([opcodes["Mov"], 4, 0])
    )
    window_start, window_end = 0x30F + profile.pointer_shift, 0x35B + profile.pointer_shift
    window_size = window_end - window_start
    replacement += bytes([jump_opcode, window_size - len(replacement)])
    replacement += bytes(window_size - len(replacement))  # Unreachable padding.
    current = bytes(data[pointer_offset + window_start:pointer_offset + window_end])
    if current != replacement:
        if (pointer[window_start].inst.name, pointer[window_start].arg1,
                pointer[window_start].arg2) != ("GetByVal", 0, 3):
            raise UnsupportedBundle("Unexpected seekbar JSX memo layout.")
        if (pointer[0x337 + profile.pointer_shift].inst.name, pointer[0x337 + profile.pointer_shift].arg1) != ("NewObject", 0):
            raise UnsupportedBundle("Unexpected seekbar wrapper props.")
        if (pointer[0x342 + profile.pointer_shift].inst.name, pointer[0x342 + profile.pointer_shift].arg1, pointer[0x342 + profile.pointer_shift].arg2) != (
            "PutNewOwnByIdShort", 0, 9
        ):
            raise UnsupportedBundle("Unexpected seekbar wrapper child.")
        if (pointer[0x346 + profile.pointer_shift].inst.name, pointer[0x346 + profile.pointer_shift].arg1) != ("Call3", 0):
            raise UnsupportedBundle("Unexpected seekbar wrapper renderer.")
    data[pointer_offset + window_start:pointer_offset + window_end] = replacement

    # TV screens do not mount a GestureHandlerRootView. The detector must be
    # inside a native gesture root, otherwise its pan/tap callbacks never run.
    # Reuse the gesture module already imported by this wrapper and put a root
    # around the detector, with forceActive for TV-focusable native children.
    load_true = data[seek_offset + 0x7A]
    root_code = (
        bytes([opcodes["LoadFromEnvironment"], 8, 1, 4])
        + bytes([opcodes["GetByIdShort"], 9, 8, 23, sid("jsx")])
        + bytes([opcodes["LoadFromEnvironment"], 8, 1, 0])
        + bytes([opcodes["LoadFromEnvironment"], 7, 1, 1])
        + bytes([get_value, 7, 7, 2])
        + bytes([opcodes["Call2"], 7, 8, 10, 7])  # require(gesture module).
        + bytes([get_id, 8, 7, 26]) + sid("GestureDetector").to_bytes(2, "little")  # GestureDetector.
        + bytes([opcodes["NewObject"], 0])
        + bytes([opcodes["PutNewOwnById"], 0, 6]) + sid("gesture").to_bytes(2, "little")
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 4, sid("children")])
        + bytes([opcodes["Call3"], 4, 9, 10, 8, 0])
        + bytes([marker[0], 8]) + sid("GestureHandlerRootView").to_bytes(4, "little")  # GestureHandlerRootView.
        + bytes([get_value, 8, 7, 8])  # Computed property: no new inline-cache slot.
        + bytes([opcodes["NewObject"], 0])
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 16, sid("style")])
        + bytes([opcodes["PutNewOwnByIdShort"], 0, 4, sid("children")])
        + bytes([load_true, 7])
        + bytes([opcodes["PutNewOwnById"], 0, 7]) + sid("unstable_forceActive").to_bytes(2, "little")
        + bytes([opcodes["Call3"], 0, 9, 10, 8, 0])
    )
    root_start, root_end = window_end, 0x3B1 + profile.pointer_shift
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

    commit_offset = expected["commit"][1]
    commit = functions["commit"]
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

    if not profile.vizbee:
        # Horizon omits VizbeeReceiverNativeManager. Forcing TV mode otherwise
        # selects the real receiver, whose one-second player-status poll calls
        # missing setPlayerAdapter/setVideoStatus methods as soon as theme music
        # starts. Select Plex's existing VizbeeNoopManager instead, covering
        # initialization, polling, and delegate teardown together. Audio/video
        # playback does not use this optional casting adapter.
        vizbee_offset = expected["vizbee_selector"][1]
        vizbee = functions["vizbee_selector"]
        for position, operands in {
            0xB0: ("GetById", 11, 1, 2, sid("isTV")),
            0xBB: ("GetByIdShort", 10, 10, 3, sid("default")),
            0xC0: ("PutNewOwnById", 1, 10, sid("VizbeeManager")),
            0x109: ("GetByIdShort", 9, 9, 3, sid("default")),
            0x10E: ("PutNewOwnById", 1, 9, sid("VizbeeManager")),
        }.items():
            ins = vizbee[position]
            actual = (ins.inst.name, *(getattr(ins, f"arg{n}") for n in range(1, len(operands))))
            if actual != operands:
                raise UnsupportedBundle("Unexpected Vizbee receiver selector.")
        replacement = bytes([jump_opcode, 3, 0])
        current = bytes(data[vizbee_offset + 0xB8:vizbee_offset + 0xBB])
        if current != replacement:
            ins = vizbee[0xB8]
            if (ins.inst.name, ins.arg1, ins.arg2) != ("JmpTrue", 81, 11):
                raise UnsupportedBundle("Unexpected Vizbee receiver selection branch.")
        data[vizbee_offset + 0xB8:vizbee_offset + 0xBB] = replacement

    data[-20:] = sha1(data[:-20]).digest()
    patched = bytes(data)
    if len(patched) != len(original):
        raise UnsupportedBundle("A fixed-size patch changed the Hermes bundle length.")
    verifier = HBCReader()
    verifier.read_whole_file(BytesIO(patched))  # Includes the Hermes footer check.
    for number, _offset, _size in expected.values():
        instructions = list(parse_hbc_bytecode(verifier.function_headers[number], verifier))
        boundaries = {ins.original_pos for ins in instructions}
        for ins in instructions:
            for index, operand in enumerate(ins.inst.operands, 1):
                if operand.operand_type.name in ("Addr8", "Addr32"):
                    target = ins.original_pos + getattr(ins, f"arg{index}")
                    if target not in boundaries:
                        raise UnsupportedBundle(f"Invalid branch target in patched function #{number}.")
    return patched
