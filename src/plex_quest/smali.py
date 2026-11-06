import re
from pathlib import Path

from . import ORIGINAL_PACKAGE, QUEST_PACKAGE
from .profiles import PROFILES


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


def patch_application(text: str, mode_reads: int = 3, vizbee: bool = True) -> str:
    descriptor = "onCreate()V"
    method = get_method(text, descriptor)
    call = re.compile(
        r"invoke-virtual \{[^}]+\}, Landroid/app/UiModeManager;->getCurrentModeType\(\)I"
        r"(?:\s|\.line \d+)*move-result (v\d+)"
    )
    method, count = call.subn(lambda m: f"const/4 {m[1]}, 0x4", method)
    if count not in (0, mode_reads):
        raise ValueError(f"Expected {mode_reads} startup UI-mode reads; found {count}.")
    if count == 0:
        compact = "\n".join(line.strip() for line in method.splitlines()
                            if line.strip() and not line.strip().startswith(".line"))
        forced = re.findall(
            r"check-cast (v\d+), Landroid/app/UiModeManager;\n"
            r"(?:(?!check-cast).+\n)*?const/4 \1, 0x4", compact
        )
        if len(forced) != mode_reads:
            raise ValueError("Unknown startup mode logic; refusing to guess.")
    anchor = "invoke-super {p0}, Landroid/app/Application;->onCreate()V"
    if anchor not in method:
        raise ValueError("Missing Application.onCreate anchor.")
    startup = method.find("Lcom/facebook/react/defaults/DefaultNewArchitectureEntryPoint;")
    early_vizbee = method.find("Ltv/vizbee/screen/api/Vizbee;->setApplication")
    if vizbee and (early_vizbee < 0 or early_vizbee > startup):
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


def patch_seek_event(text: str) -> str:
    descriptor = "emitOnKeyEvent(Landroid/view/KeyEvent;)V"
    method = get_method(text, descriptor)
    if "->questSeekStepForHold(J)I" in method:
        return text
    if ".locals 3" not in method:
        raise ValueError("Unsupported native key-event register layout.")
    anchor = "invoke-virtual {p1}, Landroid/view/KeyEvent;->getAction()I"
    if method.count(anchor) != 1 or "Arguments;->createMap()" not in method:
        raise ValueError("Missing native key-event payload anchors.")
    method = method.replace(".locals 3", ".locals 7", 1)
    # Each KeyEvent carries its original down-time, so queued JS events receive
    # the tier for that event rather than a later mutable global tier.
    insertion = (
        "invoke-virtual {p1}, Landroid/view/KeyEvent;->getEventTime()J\n"
        "    move-result-wide v3\n"
        "    invoke-virtual {p1}, Landroid/view/KeyEvent;->getDownTime()J\n"
        "    move-result-wide v5\n"
        "    sub-long/2addr v3, v5\n"
        "    invoke-static {v3, v4}, Ltv/plex/app/MainActivity;->questSeekStepForHold(J)I\n"
        "    move-result v2\n"
        "    const-string v1, \"forwardTimeMs\"\n"
        "    invoke-interface {v0, v1, v2}, Lcom/facebook/react/bridge/WritableMap;->putInt(Ljava/lang/String;I)V\n\n"
        "    "
    )
    method = method.replace(anchor, insertion + anchor, 1)
    return set_method(text, descriptor, method)


def patch_application_id(text: str) -> str:
    field = re.compile(r'(\.field public static final APPLICATION_ID:Ljava/lang/String; = )"([^"]+)"')
    matches = list(field.finditer(text))
    if len(matches) != 1 or matches[0][2] not in (ORIGINAL_PACKAGE, QUEST_PACKAGE):
        raise ValueError("Unsupported BuildConfig application ID.")
    return field.sub(lambda match: match[1] + '"' + QUEST_PACKAGE + '"', text)


def patch_smali(tree: Path):
    activity = find_class(tree, "Ltv/plex/app/MainActivity;")
    activity_source = activity.read_text()
    profiles = [profile for profile in PROFILES if profile.marker in activity_source]
    if len(profiles) != 1:
        raise ValueError("Unsupported native Plex build. Supported builds: "
                         + ", ".join(profile.label for profile in PROFILES))
    profile = profiles[0]
    app = find_class(tree, "Ltv/plex/app/MainApplication;")
    info = find_class(tree, "Lcom/facebook/react/modules/systeminfo/AndroidInfoModule;")
    keys = find_class(tree, profile.key_class)
    views = find_class(tree, "Lcom/facebook/react/views/view/ReactViewGroup;")
    config = find_class(tree, "Ltv/plex/app/BuildConfig;")
    key_events = find_class(tree, "Ltv/plex/video/KeyHandler;")
    view_text = views.read_text()
    for direction in ("Up", "Down", "Left", "Right"):
        if f".field private trapFocus{direction}:Z" not in view_text:
            raise ValueError("Unsupported React Native focus-trap fields.")
    hook = find_class(tree, profile.playback_hook).read_text()
    if ".field public static l:Lkotlin/jvm/functions/Function1;" not in hook:
        raise ValueError("Unsupported native playback input hook.")
    hit_class, hit_method = profile.hit_test.split("->")
    get_method(find_class(tree, hit_class).read_text(),
               hit_method + "([FLandroid/view/View;Ljava/util/List;)Landroid/view/View;")
    screen = find_class(tree, "Lcom/swmansion/rnscreens/Screen;").read_text()
    get_method(screen, "getActivityState()Lcom/swmansion/rnscreens/Screen$ActivityState;")
    get_method(screen, "getStackPresentation()Lcom/swmansion/rnscreens/Screen$StackPresentation;")
    get_method(find_class(tree, "Lcom/swmansion/rnscreens/ScreenStack;").read_text(),
               "getTopScreen()Lcom/swmansion/rnscreens/Screen;")
    for descriptor, member in (("ActivityState", "INACTIVE"), ("StackPresentation", "PUSH")):
        enum = find_class(tree, f"Lcom/swmansion/rnscreens/Screen${descriptor};").read_text()
        if f".field public static final enum {member}:" not in enum:
            raise ValueError("Unsupported native-screen modal state.")
    def input_template(path: Path) -> str:
        return (path.read_text().replace("LSf/d;", profile.playback_hook)
                .replace("Lcom/facebook/react/uimanager/P;->c", profile.hit_test))
    # Compute every replacement before modifying the tree.
    activity_text = patch_activity(activity_source, input_template(TEMPLATE))
    activity_text = patch_activity(activity_text, input_template(TEMPLATE.parent / "navigation-input.smali"))
    activity_text = inject_navigation_handler(activity_text, "dispatchTouchEvent(Landroid/view/MotionEvent;)Z",
                                              "questHandleNavigationTouch")
    activity_text = inject_navigation_handler(activity_text, "dispatchKeyEvent(Landroid/view/KeyEvent;)Z",
                                              "questHandleNavigationBack")
    changes = {
        key_events: patch_seek_event(key_events.read_text()),
        config: patch_application_id(config.read_text()),
        activity: activity_text,
        app: patch_application(app.read_text(), profile.startup_mode_reads, profile.vizbee),
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
    return profile
