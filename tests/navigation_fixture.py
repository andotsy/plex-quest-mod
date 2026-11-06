"""Execute the navigation template's ancestor walk and focus calls on view fixtures."""
import json
import re
from dataclasses import dataclass, field


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
    shown: bool = True
    alpha: float = 1.0
    width: int = 100
    height: int = 100

    def getTag(self):
        return self.tag

    def getParent(self):
        return self.parent

    def isClickable(self):
        return self.clickable

    def isEnabled(self):
        return self.enabled

    def isShown(self):
        return self.shown and (self.parent is None or self.parent.isShown())

    def getAlpha(self):
        return self.alpha

    def getWidth(self):
        return self.width

    def getHeight(self):
        return self.height

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


@dataclass
class ViewGroup(View):
    children: list = field(default_factory=list)

    def __post_init__(self):
        for child in self.children:
            child.parent = self

    def getChildCount(self):
        return len(self.children)

    def getChildAt(self, index):
        return self.children[index]


@dataclass
class Screen(ViewGroup):
    activity: str = "ON_TOP"
    presentation: str = "PUSH"

    def getActivityState(self):
        return self.activity

    def getStackPresentation(self):
        return self.presentation


@dataclass
class ScreenStack(ViewGroup):
    top: object = None

    def getTopScreen(self):
        return self.top


def execute(method, registers, start=None, methods=None, overrides=None):
    """Interpret actual template instructions, leaving Android hit-testing stubbed."""
    lines = [line.split("#", 1)[0].strip() for line in method.splitlines()]
    lines = [line for line in lines if line and not line.startswith(".")]
    labels = {line: index for index, line in enumerate(lines) if line.startswith(":")}
    pc = lines.index(start) if start else 0
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
            kind = {"Ljava/lang/String;": str, "Landroid/view/View;": View,
                    "Landroid/view/ViewGroup;": ViewGroup,
                    "Lcom/swmansion/rnscreens/Screen;": Screen,
                    "Lcom/swmansion/rnscreens/ScreenStack;": ScreenStack}[args[2]]
            registers[args[0]] = isinstance(registers[args[1]], kind)
        elif opcode == "move-object":
            registers[args[0]] = registers[args[1]]
        elif opcode == "sget-object":
            registers[args[0]] = args[1].split("->", 1)[1].split(":", 1)[0]
        elif opcode == "cmpg-float":
            left, right = registers[args[1]], registers[args[2]]
            registers[args[0]] = (left > right) - (left < right)
        elif opcode == "add-int/lit8":
            registers[args[0]] = registers[args[1]] + int(args[2], 0)
        elif opcode in ("move-result", "move-result-object"):
            registers[args[0]] = result
        elif opcode == "invoke-virtual":
            match = re.fullmatch(r"\{([^}]+)\}, (.+);->([^()]+)\(.*", operands)
            call_args = [registers[name.strip()] for name in match[1].split(",")]
            receiver, *parameters = call_args
            result = (receiver.startswith(*parameters) if match[3] == "startsWith"
                      else getattr(receiver, match[3])(*parameters))
        elif opcode in ("invoke-static", "invoke-direct"):
            match = re.fullmatch(r"\{([^}]+)\}, (.+);->([^()]+)\(.*", operands)
            call_args = [registers[name.strip()] for name in match[1].split(",")]
            if match[3] in (overrides or {}):
                result = overrides[match[3]](*call_args)
            else:
                result = execute(methods[match[3]], {f"p{i}": value for i, value in enumerate(call_args)},
                                 methods=methods, overrides=overrides)
        elif opcode in ("if-eqz", "if-nez"):
            truthy = bool(registers[args[0]])
            if truthy == (opcode == "if-nez"):
                pc = labels[args[1]]
        elif opcode in ("if-eq", "if-ne"):
            left, right = registers[args[0]], registers[args[1]]
            equal = left is right if isinstance(left, View) or isinstance(right, View) else left == right
            if equal == (opcode == "if-eq"):
                pc = labels[args[2]]
        elif opcode in ("if-lez", "if-ltz"):
            value = registers[args[0]]
            if (value <= 0 if opcode == "if-lez" else value < 0):
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
