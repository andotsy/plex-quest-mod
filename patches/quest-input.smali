# Original controller integration code, injected into tv.plex.app.MainActivity.
# Playback wheel events become balanced media keys; pointed-at lists scroll in pixels.

.field private static questLastScrollEvent:J
.field private static questLastSeekEvent:J
.field private static questGestureStartedAt:J
.field private static questSeekDirection:I
.field private static questTouchOnControl:Z
.field private static questTouchOnSeekbar:Z
.field private static questSuppressVerticalRepeat:Z

.method public static questSeekStepForHold(J)I
    .locals 3

    const-wide/16 v0, 0x7d0
    cmp-long v2, p0, v0
    if-ltz v2, :small
    const-wide/16 v0, 0x1388
    cmp-long v2, p0, v0
    if-ltz v2, :medium
    const v0, 0xea60
    return v0
    :medium
    const/16 v0, 0x7530
    return v0
    :small
    const/16 v0, 0x2710
    return v0
.end method

.method private final questFindDeckView(Landroid/view/View;)Landroid/view/View;
    .locals 4

    instance-of v0, p1, Lcom/facebook/react/views/view/ReactViewGroup;
    if-eqz v0, :children
    move-object v0, p1
    check-cast v0, Lcom/facebook/react/views/view/ReactViewGroup;
    invoke-virtual {v0}, Lcom/facebook/react/views/view/ReactViewGroup;->questTrapsAllFocusDirections()Z
    move-result v0
    if-eqz v0, :children
    invoke-virtual {p1}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :children
    invoke-virtual {p1}, Landroid/view/View;->getAlpha()F
    move-result v0
    const v1, 0x3c23d70a
    cmpl-float v0, v0, v1
    if-lez v0, :children
    return-object p1

    :children
    instance-of v0, p1, Landroid/view/ViewGroup;
    if-eqz v0, :absent
    check-cast p1, Landroid/view/ViewGroup;
    invoke-virtual {p1}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v0
    const/4 v1, 0x0
    :child
    if-ge v1, v0, :absent
    invoke-virtual {p1, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v2
    invoke-direct {p0, v2}, Ltv/plex/app/MainActivity;->questFindDeckView(Landroid/view/View;)Landroid/view/View;
    move-result-object v2
    if-nez v2, :present
    add-int/lit8 v1, v1, 0x1
    goto :child
    :present
    return-object v2
    :absent
    const/4 v0, 0x0
    return-object v0
.end method

.method private final questHasDeck()Z
    .locals 1

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    invoke-direct {p0, v0}, Ltv/plex/app/MainActivity;->questFindDeckView(Landroid/view/View;)Landroid/view/View;
    move-result-object v0
    if-eqz v0, :absent
    const/4 v0, 0x1
    return v0
    :absent
    const/4 v0, 0x0
    return v0
.end method

.method private final questFindDeckExit(Landroid/view/View;)Landroid/view/View;
    .locals 4

    # The native TV deck header is a full-width, 1dp close/focus target.
    # Search children first to select its actual native View, not its wrappers.
    instance-of v0, p1, Landroid/view/ViewGroup;
    if-eqz v0, :check_size
    move-object v0, p1
    check-cast v0, Landroid/view/ViewGroup;
    invoke-virtual {v0}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v1
    const/4 v2, 0x0
    :child
    if-ge v2, v1, :check_size
    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v3
    invoke-direct {p0, v3}, Ltv/plex/app/MainActivity;->questFindDeckExit(Landroid/view/View;)Landroid/view/View;
    move-result-object v3
    if-nez v3, :found
    add-int/lit8 v2, v2, 0x1
    goto :child
    :found
    return-object v3
    :check_size
    invoke-virtual {p1}, Landroid/view/View;->getHeight()I
    move-result v0
    if-lez v0, :absent
    const/4 v1, 0x3
    if-gt v0, v1, :absent
    invoke-virtual {p1}, Landroid/view/View;->getWidth()I
    move-result v0
    const/16 v1, 0x64
    if-lt v0, v1, :absent
    return-object p1
    :absent
    const/4 v0, 0x0
    return-object v0
.end method

.method private final questCloseDeckToControls()Z
    .locals 3

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    invoke-direct {p0, v0}, Ltv/plex/app/MainActivity;->questFindDeckView(Landroid/view/View;)Landroid/view/View;
    move-result-object v0
    if-eqz v0, :absent
    invoke-direct {p0, v0}, Ltv/plex/app/MainActivity;->questFindDeckExit(Landroid/view/View;)Landroid/view/View;
    move-result-object v0
    if-eqz v0, :absent
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/view/View;->setFocusable(Z)V
    invoke-virtual {v0, v1}, Landroid/view/View;->setFocusableInTouchMode(Z)V
    invoke-virtual {v0}, Landroid/view/View;->clearFocus()V
    invoke-virtual {v0}, Landroid/view/View;->requestFocusFromTouch()Z
    move-result v0
    const-string v1, "QuestPlexInput"
    const-string v2, "deck_exit_focus_requested"
    invoke-static {v1, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    return v0
    :absent
    const-string v1, "QuestPlexInput"
    const-string v2, "deck_exit_not_found"
    invoke-static {v1, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    const/4 v0, 0x0
    return v0
.end method

.method private final questOpenDeckIfVisible()Z
    .locals 4

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    const-string v1, "player-down-button"
    invoke-virtual {v0, v1}, Landroid/view/View;->findViewWithTag(Ljava/lang/Object;)Landroid/view/View;
    move-result-object v0
    if-eqz v0, :missing_arrow
    invoke-virtual {v0}, Landroid/view/View;->isShown()Z
    move-result v1
    if-eqz v1, :hidden_arrow
    move-object v1, v0
    :parent
    invoke-virtual {v1}, Landroid/view/View;->getAlpha()F
    move-result v2
    const v3, 0x3dcccccd
    cmpg-float v2, v2, v3
    if-ltz v2, :hidden_arrow
    invoke-virtual {v1}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v1
    instance-of v2, v1, Landroid/view/View;
    if-eqz v2, :activate
    check-cast v1, Landroid/view/View;
    goto :parent
    :activate
    # Generic stick events leave Android in touch mode. Enter TV focus explicitly
    # so ShowDeckButton.onFocus uses Plex's normal setDeckVisible(true) callback.
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/view/View;->setFocusableInTouchMode(Z)V
    invoke-virtual {v0}, Landroid/view/View;->clearFocus()V
    invoke-virtual {v0}, Landroid/view/View;->requestFocusFromTouch()Z
    move-result v1
    const-string v2, "QuestPlexInput"
    const-string v3, "deck_arrow_focus_requested"
    invoke-static {v2, v3}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    return v1
    :missing_arrow
    const-string v1, "QuestPlexInput"
    const-string v2, "deck_arrow_not_found"
    invoke-static {v1, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    const/4 v0, 0x0
    return v0
    :hidden_arrow
    const-string v1, "QuestPlexInput"
    const-string v2, "deck_arrow_hidden"
    invoke-static {v1, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    const/4 v0, 0x0
    return v0
.end method

.method private final questIsPlaybackControl(Landroid/view/MotionEvent;)Z
    .locals 5

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    instance-of v1, v0, Landroid/view/ViewGroup;
    if-eqz v1, :background
    move-object v1, v0
    check-cast v0, Landroid/view/ViewGroup;
    const/4 v2, 0x2
    new-array v2, v2, [F
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getX()F
    move-result v3
    const/4 v4, 0x0
    aput v3, v2, v4
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getY()F
    move-result v3
    const/4 v4, 0x1
    aput v3, v2, v4
    const/4 v3, 0x0
    invoke-static {v2, v0, v3}, Lcom/facebook/react/uimanager/P;->c([FLandroid/view/View;Ljava/util/List;)Landroid/view/View;
    move-result-object v2

    :parent
    if-eqz v2, :background
    if-eq v2, v1, :background
    invoke-virtual {v2}, Landroid/view/View;->isClickable()Z
    move-result v3
    if-eqz v3, :next_parent
    invoke-virtual {v2}, Landroid/view/View;->getWidth()I
    move-result v3
    mul-int/lit8 v3, v3, 0x4
    invoke-virtual {v1}, Landroid/view/View;->getWidth()I
    move-result v4
    mul-int/lit8 v4, v4, 0x3
    if-lt v3, v4, :control
    invoke-virtual {v2}, Landroid/view/View;->getHeight()I
    move-result v3
    mul-int/lit8 v3, v3, 0x4
    invoke-virtual {v1}, Landroid/view/View;->getHeight()I
    move-result v4
    mul-int/lit8 v4, v4, 0x3
    if-lt v3, v4, :control

    :next_parent
    invoke-virtual {v2}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v2
    instance-of v3, v2, Landroid/view/View;
    if-eqz v3, :background
    check-cast v2, Landroid/view/View;
    goto :parent

    :control
    const/4 v0, 0x1
    return v0
    :background
    const/4 v0, 0x0
    return v0
.end method

.method private final questScrollAtPointer(Landroid/view/MotionEvent;)Z
    .locals 7

    const/16 v0, 0xa
    invoke-virtual {p1, v0}, Landroid/view/MotionEvent;->getAxisValue(I)F
    move-result v1
    const/16 v0, 0x9
    invoke-virtual {p1, v0}, Landroid/view/MotionEvent;->getAxisValue(I)F
    move-result v2
    invoke-static {v1}, Ljava/lang/Math;->abs(F)F
    move-result v3
    invoke-static {v2}, Ljava/lang/Math;->abs(F)F
    move-result v4
    const v0, 0x3d23d70a
    cmpl-float v5, v3, v4
    if-lez v5, :vertical_axis
    cmpg-float v5, v3, v0
    if-ltz v5, :no_scroll
    const/4 v5, 0x1
    goto :find_target

    :vertical_axis
    cmpg-float v5, v4, v0
    if-ltz v5, :no_scroll
    const/4 v5, 0x0

    :find_target
    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    instance-of v3, v0, Landroid/view/ViewGroup;
    if-eqz v3, :no_scroll
    check-cast v0, Landroid/view/ViewGroup;
    const/4 v3, 0x2
    new-array v3, v3, [F
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getX()F
    move-result v4
    const/4 v6, 0x0
    aput v4, v3, v6
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getY()F
    move-result v4
    const/4 v6, 0x1
    aput v4, v3, v6
    const/4 v4, 0x0
    invoke-static {v3, v0, v4}, Lcom/facebook/react/uimanager/P;->c([FLandroid/view/View;Ljava/util/List;)Landroid/view/View;
    move-result-object v0

    :scroll_parent
    if-eqz v0, :no_scroll
    if-eqz v5, :check_vertical
    instance-of v3, v0, Landroid/widget/HorizontalScrollView;
    if-eqz v3, :next_parent
    const/4 v3, 0x1
    invoke-virtual {v0, v3}, Landroid/view/View;->canScrollHorizontally(I)Z
    move-result v3
    if-nez v3, :scroll_horizontal
    const/4 v3, -0x1
    invoke-virtual {v0, v3}, Landroid/view/View;->canScrollHorizontally(I)Z
    move-result v3
    if-eqz v3, :next_parent

    :scroll_horizontal
    move v2, v1
    neg-float v2, v2
    goto :scroll_pixels

    :check_vertical
    instance-of v3, v0, Landroid/widget/ScrollView;
    if-eqz v3, :next_parent
    const/4 v3, 0x1
    invoke-virtual {v0, v3}, Landroid/view/View;->canScrollVertically(I)Z
    move-result v3
    if-nez v3, :scroll_pixels
    const/4 v3, -0x1
    invoke-virtual {v0, v3}, Landroid/view/View;->canScrollVertically(I)Z
    move-result v3
    if-eqz v3, :next_parent

    :scroll_pixels
    invoke-virtual {v0}, Landroid/view/View;->getResources()Landroid/content/res/Resources;
    move-result-object v3
    invoke-virtual {v3}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v3
    iget v3, v3, Landroid/util/DisplayMetrics;->density:F
    const/high16 v4, 0x42800000
    mul-float/2addr v3, v4
    mul-float/2addr v2, v3
    neg-float v2, v2
    invoke-static {v2}, Ljava/lang/Math;->round(F)I
    move-result v3
    const/4 v4, 0x0
    if-eqz v5, :apply_vertical
    invoke-virtual {v0, v3, v4}, Landroid/view/View;->scrollBy(II)V
    goto :did_scroll
    :apply_vertical
    invoke-virtual {v0, v4, v3}, Landroid/view/View;->scrollBy(II)V
    :did_scroll
    const/4 v0, 0x1
    return v0

    :next_parent
    invoke-virtual {v0}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    instance-of v3, v0, Landroid/view/View;
    if-eqz v3, :no_scroll
    check-cast v0, Landroid/view/View;
    goto :scroll_parent
    :no_scroll
    const/4 v0, 0x0
    return v0
.end method

.method public final dispatchGenericMotionEvent(Landroid/view/MotionEvent;)Z
    .locals 13

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getActionMasked()I
    move-result v0
    const/16 v1, 0x8
    if-ne v0, v1, :super_motion
    const/4 v12, 0x0
    sget-object v0, LSf/d;->l:Lkotlin/jvm/functions/Function1;
    if-eqz v0, :pointer_scroll
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questHasDeck()Z
    move-result v12
    if-eqz v12, :pointer_scroll
    # Up/down enters or leaves the deck. Horizontal motion keeps native pixel
    # scrolling when the pointer is over the episode row.
    const/16 v0, 0xa
    invoke-virtual {p1, v0}, Landroid/view/MotionEvent;->getAxisValue(I)F
    move-result v0
    invoke-static {v0}, Ljava/lang/Math;->abs(F)F
    move-result v1
    const/16 v0, 0x9
    invoke-virtual {p1, v0}, Landroid/view/MotionEvent;->getAxisValue(I)F
    move-result v0
    invoke-static {v0}, Ljava/lang/Math;->abs(F)F
    move-result v0
    cmpl-float v0, v0, v1
    if-gtz v0, :playback_motion
    :pointer_scroll
    invoke-direct {p0, p1}, Ltv/plex/app/MainActivity;->questScrollAtPointer(Landroid/view/MotionEvent;)Z
    move-result v0
    if-nez v0, :consume
    if-nez v12, :playback_motion
    sget-object v0, LSf/d;->l:Lkotlin/jvm/functions/Function1;
    if-eqz v0, :super_motion

    :playback_motion
    const/16 v0, 0xa
    invoke-virtual {p1, v0}, Landroid/view/MotionEvent;->getAxisValue(I)F
    move-result v1
    invoke-static {v1}, Ljava/lang/Math;->abs(F)F
    move-result v2
    const/16 v0, 0x9
    invoke-virtual {p1, v0}, Landroid/view/MotionEvent;->getAxisValue(I)F
    move-result v3
    invoke-static {v3}, Ljava/lang/Math;->abs(F)F
    move-result v4
    cmpl-float v0, v4, v2
    if-lez v0, :horizontal
    const v0, 0x3d23d70a
    cmpg-float v11, v4, v0
    if-ltz v11, :neutral
    const/4 v0, 0x0
    cmpl-float v11, v3, v0
    if-lez v11, :down
    const/4 v5, -0x2
    const/16 v6, 0x13
    goto :vertical_interval
    :down
    const/4 v5, 0x2
    const/16 v6, 0x14
    :vertical_interval
    const-wide/16 v7, 0x190
    goto :timing

    :horizontal
    const v0, 0x3d23d70a
    cmpg-float v11, v2, v0
    if-ltz v11, :neutral
    const/4 v0, 0x0
    cmpg-float v11, v1, v0
    if-ltz v11, :negative_horizontal
    const/4 v5, -0x1
    const/16 v6, 0x5a
    if-eqz v12, :horizontal_interval
    const/16 v6, 0x16
    goto :horizontal_interval
    :negative_horizontal
    const/4 v5, 0x1
    const/16 v6, 0x59
    if-eqz v12, :horizontal_interval
    const/16 v6, 0x15
    :horizontal_interval
    # Repeat at a stable cadence; jump distance grows with elapsed hold time.
    const-wide/16 v7, 0x1f4

    :timing
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getEventTime()J
    move-result-wide v9
    sget-wide v0, Ltv/plex/app/MainActivity;->questLastScrollEvent:J
    sub-long v0, v9, v0
    sput-wide v9, Ltv/plex/app/MainActivity;->questLastScrollEvent:J
    const-wide/16 v2, 0xc8
    cmp-long v4, v0, v2
    if-gtz v4, :new_gesture
    sget v0, Ltv/plex/app/MainActivity;->questSeekDirection:I
    if-ne v0, v5, :new_gesture
    sget-boolean v0, Ltv/plex/app/MainActivity;->questSuppressVerticalRepeat:Z
    if-eqz v0, :repeat_interval
    const/4 v0, 0x2
    if-eq v5, v0, :consume
    const/4 v0, -0x2
    if-eq v5, v0, :consume
    :repeat_interval
    sget-wide v0, Ltv/plex/app/MainActivity;->questLastSeekEvent:J
    sub-long v2, v9, v0
    cmp-long v0, v2, v7
    if-ltz v0, :consume
    goto :emit

    :new_gesture
    sput-wide v9, Ltv/plex/app/MainActivity;->questGestureStartedAt:J
    const/4 v0, 0x0
    sput-boolean v0, Ltv/plex/app/MainActivity;->questSuppressVerticalRepeat:Z
    const/4 v0, -0x2
    if-ne v5, v0, :new_down
    if-eqz v12, :emit
    const/4 v0, 0x1
    sput-boolean v0, Ltv/plex/app/MainActivity;->questSuppressVerticalRepeat:Z
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questCloseDeckToControls()Z
    move-result v0
    if-eqz v0, :emit
    sput v5, Ltv/plex/app/MainActivity;->questSeekDirection:I
    sput-wide v9, Ltv/plex/app/MainActivity;->questLastSeekEvent:J
    goto :consume

    :new_down
    const/4 v0, 0x2
    if-ne v5, v0, :emit
    if-nez v12, :emit
    const/4 v0, 0x1
    sput-boolean v0, Ltv/plex/app/MainActivity;->questSuppressVerticalRepeat:Z
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questOpenDeckIfVisible()Z
    move-result v0
    if-eqz v0, :emit
    sput v5, Ltv/plex/app/MainActivity;->questSeekDirection:I
    sput-wide v9, Ltv/plex/app/MainActivity;->questLastSeekEvent:J
    goto :consume

    :emit
    sput v5, Ltv/plex/app/MainActivity;->questSeekDirection:I
    sput-wide v9, Ltv/plex/app/MainActivity;->questLastSeekEvent:J
    new-instance v0, Landroid/view/KeyEvent;
    sget-wide v1, Ltv/plex/app/MainActivity;->questGestureStartedAt:J
    move-wide v3, v9
    const/4 v5, 0x0
    const/4 v7, 0x0
    invoke-direct/range {v0 .. v7}, Landroid/view/KeyEvent;-><init>(JJIII)V
    invoke-virtual {p0, v0}, Ltv/plex/app/MainActivity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    new-instance v0, Landroid/view/KeyEvent;
    const/4 v5, 0x1
    invoke-direct/range {v0 .. v7}, Landroid/view/KeyEvent;-><init>(JJIII)V
    invoke-virtual {p0, v0}, Ltv/plex/app/MainActivity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    goto :consume
    :neutral
    const/4 v0, 0x0
    sput v0, Ltv/plex/app/MainActivity;->questSeekDirection:I
    sput-boolean v0, Ltv/plex/app/MainActivity;->questSuppressVerticalRepeat:Z
    :consume
    const/4 v0, 0x1
    return v0
    :super_motion
    invoke-super {p0, p1}, Landroid/app/Activity;->dispatchGenericMotionEvent(Landroid/view/MotionEvent;)Z
    move-result v0
    return v0
.end method

.method private final questIsSeekbarTouch(Landroid/view/MotionEvent;)Z
    .locals 5

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    instance-of v1, v0, Landroid/view/ViewGroup;
    if-eqz v1, :absent
    check-cast v0, Landroid/view/ViewGroup;
    const/4 v1, 0x2
    new-array v1, v1, [F
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getX()F
    move-result v2
    const/4 v3, 0x0
    aput v2, v1, v3
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getY()F
    move-result v2
    const/4 v3, 0x1
    aput v2, v1, v3
    const/4 v2, 0x0
    invoke-static {v1, v0, v2}, Lcom/facebook/react/uimanager/P;->c([FLandroid/view/View;Ljava/util/List;)Landroid/view/View;
    move-result-object v0
    :parent
    if-eqz v0, :absent
    invoke-virtual {v0}, Landroid/view/View;->getTag()Ljava/lang/Object;
    move-result-object v1
    const-string v2, "SeekbarView"
    invoke-virtual {v2, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1
    if-nez v1, :found
    invoke-virtual {v0}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    instance-of v1, v0, Landroid/view/View;
    if-eqz v1, :absent
    check-cast v0, Landroid/view/View;
    goto :parent
    :found
    const/4 v0, 0x1
    return v0
    :absent
    const/4 v0, 0x0
    return v0
.end method

.method public final dispatchTouchEvent(Landroid/view/MotionEvent;)Z
    .locals 6

    sget-object v0, LSf/d;->l:Lkotlin/jvm/functions/Function1;
    if-eqz v0, :normal_touch
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getActionMasked()I
    move-result v1
    if-nez v1, :touch_up
    invoke-direct {p0, p1}, Ltv/plex/app/MainActivity;->questIsSeekbarTouch(Landroid/view/MotionEvent;)Z
    move-result v0
    sput-boolean v0, Ltv/plex/app/MainActivity;->questTouchOnSeekbar:Z
    if-eqz v0, :classify_control
    const-string v1, "QuestPlexInput"
    const-string v2, "seekbar_pointer_down"
    invoke-static {v1, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    const/4 v0, 0x1
    sput-boolean v0, Ltv/plex/app/MainActivity;->questTouchOnControl:Z
    goto :normal_touch
    :classify_control
    invoke-direct {p0, p1}, Ltv/plex/app/MainActivity;->questIsPlaybackControl(Landroid/view/MotionEvent;)Z
    move-result v0
    sput-boolean v0, Ltv/plex/app/MainActivity;->questTouchOnControl:Z
    goto :normal_touch
    :touch_up
    const/4 v0, 0x1
    if-ne v1, v0, :normal_touch
    sget-boolean v0, Ltv/plex/app/MainActivity;->questTouchOnControl:Z
    if-nez v0, :normal_touch
    invoke-static {p1}, Landroid/view/MotionEvent;->obtain(Landroid/view/MotionEvent;)Landroid/view/MotionEvent;
    move-result-object v0
    const/4 v1, 0x3
    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->setAction(I)V
    invoke-super {p0, v0}, Landroid/app/Activity;->dispatchTouchEvent(Landroid/view/MotionEvent;)Z
    invoke-virtual {v0}, Landroid/view/MotionEvent;->recycle()V
    new-instance v0, Landroid/view/KeyEvent;
    const/4 v1, 0x0
    const/16 v2, 0x55
    invoke-direct {v0, v1, v2}, Landroid/view/KeyEvent;-><init>(II)V
    invoke-virtual {p0, v0}, Ltv/plex/app/MainActivity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    new-instance v0, Landroid/view/KeyEvent;
    const/4 v1, 0x1
    invoke-direct {v0, v1, v2}, Landroid/view/KeyEvent;-><init>(II)V
    invoke-virtual {p0, v0}, Ltv/plex/app/MainActivity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    const/4 v0, 0x1
    return v0

    :normal_touch
    invoke-super {p0, p1}, Landroid/app/Activity;->dispatchTouchEvent(Landroid/view/MotionEvent;)Z
    move-result v0
    sget-object v1, LSf/d;->l:Lkotlin/jvm/functions/Function1;
    if-eqz v1, :return_touch
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getActionMasked()I
    move-result v1
    const/4 v2, 0x1
    if-ne v1, v2, :return_touch
    # The timeline's native pointer gesture already seeks to the clicked point.
    # An extra DPAD_CENTER would also activate a TV control after that seek.
    sget-boolean v1, Ltv/plex/app/MainActivity;->questTouchOnSeekbar:Z
    if-eqz v1, :confirm_control
    const-string v1, "QuestPlexInput"
    const-string v2, "seekbar_pointer_up"
    invoke-static {v1, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    const/4 v1, 0x0
    sput-boolean v1, Ltv/plex/app/MainActivity;->questTouchOnSeekbar:Z
    goto :return_touch
    :confirm_control
    new-instance v1, Landroid/view/KeyEvent;
    const/4 v2, 0x0
    const/16 v3, 0x17
    invoke-direct {v1, v2, v3}, Landroid/view/KeyEvent;-><init>(II)V
    invoke-virtual {p0, v1}, Ltv/plex/app/MainActivity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    new-instance v1, Landroid/view/KeyEvent;
    const/4 v2, 0x1
    invoke-direct {v1, v2, v3}, Landroid/view/KeyEvent;-><init>(II)V
    invoke-virtual {p0, v1}, Ltv/plex/app/MainActivity;->dispatchKeyEvent(Landroid/view/KeyEvent;)Z
    const/4 v0, 0x1
    :return_touch
    return v0
.end method
