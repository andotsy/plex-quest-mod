import re
from pathlib import Path

from . import ORIGINAL_PACKAGE, QUEST_PACKAGE


TEMPLATE = Path(__file__).resolve().parents[2] / "patches/quest-input.smali"
METHOD = re.compile(r"^\.method[^\n]*\n.*?^\.end method[ \t]*$", re.M | re.S)


def find_class(tree: Path, descriptor: str) -> Path:
    relative = descriptor.removeprefix("L").removesuffix(";")
    candidates = list(tree.glob(f"smali*/{relative}.smali"))
    if not candidates:
        parent, name = relative.rsplit("/", 1)
        candidates = list(tree.glob(f"smali*/{parent}*/{name}*.smali"))
    for path in candidates:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        if first_line.endswith(" " + descriptor):
            return path
    raise ValueError(f"Missing supported class: {descriptor}")


def get_method(text: str, descriptor: str) -> str:
    found = [match.group() for match in METHOD.finditer(text)
             if match.group().splitlines()[0].endswith(" " + descriptor)]
    if len(found) != 1:
        raise ValueError(f"Expected one method: {descriptor}")
    return found[0]


def set_method(text: str, descriptor: str, replacement: str) -> str:
    for match in METHOD.finditer(text):
        if match.group().splitlines()[0].endswith(" " + descriptor):
            return text[:match.start()] + replacement + text[match.end():]
    return text.rstrip() + "\n\n" + replacement + "\n"


def patch_activity(text: str, template: str) -> str:
    for field in re.findall(r"^\.field[^\n]+", template, re.M):
        name = field.split()[-1].split(":")[0]
        text = re.sub(rf"^\.field[^\n]*\b{re.escape(name)}:[^\n]*\n?", "", text, flags=re.M)
    fields = "\n".join(re.findall(r"^\.field[^\n]+", template, re.M))
    first_method = text.index(".method ")
    text = text[:first_method] + fields + "\n\n" + text[first_method:]
    for match in METHOD.finditer(template):
        replacement = match.group()
        descriptor = replacement.splitlines()[0].split()[-1]
        text = set_method(text, descriptor, replacement)
    return text


def inject_navigation_handler(text: str, descriptor: str, handler: str) -> str:
    method = get_method(text, descriptor)
    marker = f":quest_original_{handler}"
    if marker in method:
        return text
    locals_match = re.search(r"\.locals (\d+)", method)
    if not locals_match or int(locals_match[1]) < 1:
        raise ValueError("Unsupported input-dispatch register layout.")
    event_type = "Landroid/view/KeyEvent;" if "Back" in handler else "Landroid/view/MotionEvent;"
    prologue = (
        f"\n\n    invoke-direct {{p0, p1}}, Ltv/plex/app/MainActivity;->{handler}({event_type})Z"
        f"\n    move-result v0\n    if-eqz v0, {marker}"
        f"\n    const/4 v0, 0x1\n    return v0\n    {marker}\n"
    )
    method = method[:locals_match.end()] + prologue + method[locals_match.end():]
    return set_method(text, descriptor, method)


def patch_application(text: str) -> str:
    descriptor = "onCreate()V"
    method = get_method(text, descriptor)
    call = re.compile(
        r"invoke-virtual \{[^}]+\}, Landroid/app/UiModeManager;->getCurrentModeType\(\)I"
        r"(?:\s|\.line \d+)*move-result (v\d+)"
    )
    method, count = call.subn(lambda m: f"const/4 {m[1]}, 0x4", method)
    if count not in (0, 3):
        raise ValueError(f"Expected three startup UI-mode reads; found {count}.")
    if count == 0:
        compact = "\n".join(line.strip() for line in method.splitlines()
                            if line.strip() and not line.strip().startswith(".line"))
        forced = re.findall(
            r"check-cast (v\d+), Landroid/app/UiModeManager;\n"
            r"(?:(?!check-cast).+\n)*?const/4 \1, 0x4", compact
        )
        if len(forced) != 3:
            raise ValueError("Unknown startup mode logic; refusing to guess.")
    anchor = "invoke-super {p0}, Landroid/app/Application;->onCreate()V"
    if anchor not in method:
        raise ValueError("Missing Application.onCreate anchor.")
    startup = method.find("Lcom/facebook/react/defaults/DefaultNewArchitectureEntryPoint;")
    early_vizbee = method.find("Ltv/vizbee/screen/api/Vizbee;->setApplication")
    if early_vizbee < 0 or early_vizbee > startup:
        initialization = (
            "\n\n    invoke-static {}, Ltv/vizbee/screen/api/Vizbee;->getInstance()Ltv/vizbee/screen/api/Vizbee;"
            "\n    move-result-object v0"
            "\n    invoke-virtual {v0, p0}, Ltv/vizbee/screen/api/Vizbee;->setApplication(Landroid/app/Application;)V"
        )
        method = method.replace(anchor, anchor + initialization, 1)
    return set_method(text, descriptor, method)


def patch_key_mapping(text: str) -> str:
    descriptor = "b(Landroid/view/KeyEvent;)Ljava/lang/String;"
    method = get_method(text, descriptor)
    if all(f", {code}" in method for code in ("0x60", "0x6a", "0x6b")):
        return text  # This controller mapping is already present.
    result = re.search(r"getKeyCode\(\)I(?:\s|\.line \d+)*move-result (\w+)", method)
    if not result:
        raise ValueError("Missing key-code mapping anchor.")
    play = method.index('"playOrPause"')
    labels = re.findall(r"^\s*(:[\w]+)\s*$", method[:play], re.M)
    if not labels:
        raise ValueError("Missing play/pause branch.")
    locals_match = re.search(r"\.locals (\d+)", method)
    if not locals_match:
        raise ValueError("Unsupported key-map register declaration.")
    scratch = f"v{locals_match[1]}"
    insertion = "\n" + "\n".join(
        f"    const/16 {scratch}, {code}\n    if-eq {result[1]}, {scratch}, {labels[-1]}"
        for code in ("0x60", "0x6a", "0x6b")
    )
    method = method[:result.end()] + insertion + method[result.end():]
    method = re.sub(r"\.locals \d+", f".locals {int(locals_match[1]) + 1}", method, count=1)
    return set_method(text, descriptor, method)


def patch_application_id(text: str) -> str:
    field = re.compile(r'(\.field public static final APPLICATION_ID:Ljava/lang/String; = )"([^"]+)"')
    matches = list(field.finditer(text))
    if len(matches) != 1 or matches[0][2] not in (ORIGINAL_PACKAGE, QUEST_PACKAGE):
        raise ValueError("Unsupported BuildConfig application ID.")
    return field.sub(lambda match: match[1] + '"' + QUEST_PACKAGE + '"', text)


def patch_smali(tree: Path) -> None:
    activity = find_class(tree, "Ltv/plex/app/MainActivity;")
    app = find_class(tree, "Ltv/plex/app/MainApplication;")
    info = find_class(tree, "Lcom/facebook/react/modules/systeminfo/AndroidInfoModule;")
    keys = find_class(tree, "LTf/a;")
    views = find_class(tree, "Lcom/facebook/react/views/view/ReactViewGroup;")
    config = find_class(tree, "Ltv/plex/app/BuildConfig;")
    view_text = views.read_text()
    for direction in ("Up", "Down", "Left", "Right"):
        if f".field private trapFocus{direction}:Z" not in view_text:
            raise ValueError("Unsupported React Native focus-trap fields.")
    if "PlexReactNative-2026.17.0 (971050399)_playRelease" not in activity.read_text():
        raise ValueError("Only the Plex 2026.17.0 / 971050399 play build is supported.")
    # Compute every replacement before modifying the tree.
    activity_text = patch_activity(activity.read_text(), TEMPLATE.read_text())
    activity_text = patch_activity(activity_text, (TEMPLATE.parent / "navigation-input.smali").read_text())
    activity_text = inject_navigation_handler(activity_text, "dispatchTouchEvent(Landroid/view/MotionEvent;)Z",
                                              "questHandleNavigationTouch")
    activity_text = inject_navigation_handler(activity_text, "dispatchKeyEvent(Landroid/view/KeyEvent;)Z",
                                              "questHandleNavigationBack")
    changes = {
        config: patch_application_id(config.read_text()),
        activity: activity_text,
        app: patch_application(app.read_text()),
        info: set_method(info.read_text(), "uiMode()Ljava/lang/String;",
                         '.method private final uiMode()Ljava/lang/String;\n'
                         '    .locals 1\n    const-string v0, "tv"\n'
                         '    return-object v0\n.end method'),
        keys: patch_key_mapping(keys.read_text()),
        views: set_method(view_text, "questTrapsAllFocusDirections()Z",
                          get_method((TEMPLATE.parent / "react-viewgroup-deck.smali").read_text(),
                                     "questTrapsAllFocusDirections()Z")),
    }
    for path, text in changes.items():
        path.write_text(text, encoding="utf-8")
