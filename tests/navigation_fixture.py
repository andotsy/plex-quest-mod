"""Execute the navigation template's ancestor walk and focus calls on view fixtures."""
import json
import re
from dataclasses import dataclass


@dataclass
class View:
    tag: object = None
    parent: object = None
    clickable: bool = True
    enabled: bool = True
    focused: bool = False
    touch_focusable: bool = False
    focus_events: int = 0
    clears: int = 0

    def getTag(self):
        return self.tag

    def getParent(self):
        return self.parent

    def isClickable(self):
        return self.clickable

    def isEnabled(self):
        return self.enabled

    def setFocusableInTouchMode(self, enabled):
        self.touch_focusable = bool(enabled)

    def clearFocus(self):
        self.clears += 1
        self.focused = False

    def requestFocusFromTouch(self):
        if not self.focused:
            self.focus_events += 1
        self.focused = True
        return True


def execute(method, registers, start):
    """Interpret actual template instructions, leaving Android hit-testing stubbed."""
    lines = [line.split("#", 1)[0].strip() for line in method.splitlines()]
    lines = [line for line in lines if line and not line.startswith(".")]
    labels = {line: index for index, line in enumerate(lines) if line.startswith(":")}
    pc = lines.index(start)
    result = None
    for _ in range(500):
        line = lines[pc]
        pc += 1
        if line.startswith(":") or line.startswith("check-cast "):
            continue
        opcode, operands = line.split(" ", 1)
        args = [value.strip() for value in operands.split(",")]
        if opcode == "const-string":
            registers[args[0]] = json.loads(args[1])
        elif opcode == "const/4":
            registers[args[0]] = int(args[1], 0)
        elif opcode == "instance-of":
            kind = str if args[2] == "Ljava/lang/String;" else View
            registers[args[0]] = isinstance(registers[args[1]], kind)
        elif opcode in ("move-result", "move-result-object"):
            registers[args[0]] = result
        elif opcode == "invoke-virtual":
            match = re.fullmatch(r"\{([^}]+)\}, (.+);->([^()]+)\(.*", operands)
            call_args = [registers[name.strip()] for name in match[1].split(",")]
            receiver, *parameters = call_args
            result = (receiver.startswith(*parameters) if match[3] == "startsWith"
                      else getattr(receiver, match[3])(*parameters))
        elif opcode in ("if-eqz", "if-nez"):
            truthy = bool(registers[args[0]])
            if truthy == (opcode == "if-nez"):
                pc = labels[args[1]]
        elif opcode == "goto":
            pc = labels[args[0]]
        elif opcode == "iput-object":
            field = args[2].split("->", 1)[1].split(":", 1)[0]
            registers[args[1]][field] = registers[args[0]]
        elif opcode in ("return", "return-object"):
            value = registers[args[0]]
            return None if opcode == "return-object" and value == 0 else value
        else:
            raise AssertionError(f"Unsupported navigation fixture instruction: {line}")
    raise AssertionError("Navigation template did not return")
