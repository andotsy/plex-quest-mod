# Pointer-to-TV focus integration for the top navigation popover.
.field private questNavigationAnchor:Landroid/view/View;
.field private questConsumeNavigationTouch:Z
.field private questConsumeNavigationBack:Z

.method private static questNavigationViewVisible(Landroid/view/View;)Z
    .locals 4

    if-eqz p0, :absent
    invoke-virtual {p0}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :absent
    invoke-virtual {p0}, Landroid/view/View;->getWidth()I
    move-result v0
    if-lez v0, :absent
    invoke-virtual {p0}, Landroid/view/View;->getHeight()I
    move-result v0
    if-lez v0, :absent
    :parents
    invoke-virtual {p0}, Landroid/view/View;->getAlpha()F
    move-result v1
    const/4 v2, 0x0
    cmpg-float v1, v1, v2
    if-lez v1, :absent
    instance-of v0, p0, Lcom/swmansion/rnscreens/Screen;
    if-eqz v0, :parent
    move-object v3, p0
    check-cast v3, Lcom/swmansion/rnscreens/Screen;
    invoke-virtual {v3}, Lcom/swmansion/rnscreens/Screen;->getActivityState()Lcom/swmansion/rnscreens/Screen$ActivityState;
    move-result-object v3
    sget-object v2, Lcom/swmansion/rnscreens/Screen$ActivityState;->INACTIVE:Lcom/swmansion/rnscreens/Screen$ActivityState;
    if-eq v3, v2, :absent
    :parent
    invoke-virtual {p0}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v3
    instance-of v0, v3, Landroid/view/View;
    if-eqz v0, :found
    move-object p0, v3
    check-cast p0, Landroid/view/View;
    goto :parents
    :found
    const/4 v0, 0x1
    return v0
    :absent
    const/4 v0, 0x0
    return v0
.end method

# Native-stack modals cover navigation underneath them. Search in drawing order
# and ignore inactive screens, including modals retained in an old screen tree.
.method private static questTopNavigationModal(Landroid/view/View;)Landroid/view/View;
    .locals 4

    if-eqz p0, :absent
    invoke-virtual {p0}, Landroid/view/View;->isShown()Z
    move-result v0
    if-eqz v0, :absent
    invoke-virtual {p0}, Landroid/view/View;->getAlpha()F
    move-result v0
    const/4 v1, 0x0
    cmpg-float v0, v0, v1
    if-lez v0, :absent
    invoke-virtual {p0}, Landroid/view/View;->getWidth()I
    move-result v0
    if-lez v0, :absent
    invoke-virtual {p0}, Landroid/view/View;->getHeight()I
    move-result v0
    if-lez v0, :absent
    instance-of v0, p0, Lcom/swmansion/rnscreens/Screen;
    if-eqz v0, :children
    move-object v0, p0
    check-cast v0, Lcom/swmansion/rnscreens/Screen;
    invoke-virtual {v0}, Lcom/swmansion/rnscreens/Screen;->getActivityState()Lcom/swmansion/rnscreens/Screen$ActivityState;
    move-result-object v0
    sget-object v1, Lcom/swmansion/rnscreens/Screen$ActivityState;->INACTIVE:Lcom/swmansion/rnscreens/Screen$ActivityState;
    if-eq v0, v1, :absent
    :children
    instance-of v0, p0, Lcom/swmansion/rnscreens/ScreenStack;
    if-eqz v0, :view_children
    move-object v0, p0
    check-cast v0, Lcom/swmansion/rnscreens/ScreenStack;
    invoke-virtual {v0}, Lcom/swmansion/rnscreens/ScreenStack;->getTopScreen()Lcom/swmansion/rnscreens/Screen;
    move-result-object v2
    if-eqz v2, :absent
    invoke-static {v2}, Ltv/plex/app/MainActivity;->questTopNavigationModal(Landroid/view/View;)Landroid/view/View;
    move-result-object v2
    return-object v2
    :view_children
    instance-of v0, p0, Landroid/view/ViewGroup;
    if-eqz v0, :presentation
    move-object v0, p0
    check-cast v0, Landroid/view/ViewGroup;
    invoke-virtual {v0}, Landroid/view/ViewGroup;->getChildCount()I
    move-result v1
    :child
    add-int/lit8 v1, v1, -0x1
    if-ltz v1, :presentation
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v2
    invoke-static {v2}, Ltv/plex/app/MainActivity;->questTopNavigationModal(Landroid/view/View;)Landroid/view/View;
    move-result-object v2
    if-eqz v2, :child
    return-object v2
    :presentation
    instance-of v0, p0, Lcom/swmansion/rnscreens/Screen;
    if-eqz v0, :absent
    move-object v0, p0
    check-cast v0, Lcom/swmansion/rnscreens/Screen;
    invoke-virtual {v0}, Lcom/swmansion/rnscreens/Screen;->getStackPresentation()Lcom/swmansion/rnscreens/Screen$StackPresentation;
    move-result-object v0
    sget-object v1, Lcom/swmansion/rnscreens/Screen$StackPresentation;->PUSH:Lcom/swmansion/rnscreens/Screen$StackPresentation;
    if-eq v0, v1, :absent
    return-object p0
    :absent
    const/4 v0, 0x0
    return-object v0
.end method

.method private final questNavigationModal()Landroid/view/View;
    .locals 1

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    invoke-static {v0}, Ltv/plex/app/MainActivity;->questTopNavigationModal(Landroid/view/View;)Landroid/view/View;
    move-result-object v0
    return-object v0
.end method

.method private final questNavigationPopover()Landroid/view/View;
    .locals 3

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    const-string v1, "secondary-navigation"
    invoke-virtual {v0, v1}, Landroid/view/View;->findViewWithTag(Ljava/lang/Object;)Landroid/view/View;
    move-result-object v0
    if-eqz v0, :absent
    invoke-static {v0}, Ltv/plex/app/MainActivity;->questNavigationViewVisible(Landroid/view/View;)Z
    move-result v1
    if-eqz v1, :absent
    return-object v0
    :absent
    const/4 v0, 0x0
    return-object v0
.end method

.method private final questPointedNavigationItem(Landroid/view/MotionEvent;)Landroid/view/View;
    .locals 7

    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    invoke-virtual {v0}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v0
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questNavigationModal()Landroid/view/View;
    move-result-object v4
    if-eqz v4, :root
    move-object v0, v4
    :root
    instance-of v1, v0, Landroid/view/ViewGroup;
    if-eqz v1, :absent
    check-cast v0, Landroid/view/ViewGroup;
    const/4 v1, 0x2
    new-array v1, v1, [F
    const/4 v5, 0x2
    new-array v5, v5, [I
    invoke-virtual {v0, v5}, Landroid/view/View;->getLocationInWindow([I)V
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getX()F
    move-result v2
    const/4 v3, 0x0
    aget v6, v5, v3
    int-to-float v6, v6
    sub-float/2addr v2, v6
    aput v2, v1, v3
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getY()F
    move-result v2
    const/4 v3, 0x1
    aget v6, v5, v3
    int-to-float v6, v6
    sub-float/2addr v2, v6
    aput v2, v1, v3
    const/4 v2, 0x0
    invoke-static {v1, v0, v2}, Lcom/facebook/react/uimanager/P;->c([FLandroid/view/View;Ljava/util/List;)Landroid/view/View;
    move-result-object v0
    :parent
    if-eqz v0, :absent
    if-nez v4, :navigation_item
    invoke-virtual {v0}, Landroid/view/View;->getTag()Ljava/lang/Object;
    move-result-object v1
    instance-of v2, v1, Ljava/lang/String;
    if-eqz v2, :next
    check-cast v1, Ljava/lang/String;
    const-string v2, "primary-navigation-"
    invoke-virtual {v1, v2}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v2
    if-nez v2, :navigation_item
    const-string v2, "secondary-navigation-"
    invoke-virtual {v1, v2}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v2
    if-eqz v2, :next
    :navigation_item
    invoke-virtual {v0}, Landroid/view/View;->isClickable()Z
    move-result v1
    if-eqz v1, :next
    invoke-virtual {v0}, Landroid/view/View;->isEnabled()Z
    move-result v1
    if-eqz v1, :next
    invoke-static {v0}, Ltv/plex/app/MainActivity;->questNavigationViewVisible(Landroid/view/View;)Z
    move-result v1
    if-nez v1, :found
    :next
    if-eq v0, v4, :absent
    invoke-virtual {v0}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    instance-of v1, v0, Landroid/view/View;
    if-eqz v1, :absent
    check-cast v0, Landroid/view/View;
    goto :parent
    :found
    return-object v0
    :absent
    const/4 v0, 0x0
    return-object v0
.end method

.method private final questDismissNavigationPopover()Z
    .locals 2

    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questNavigationPopover()Landroid/view/View;
    move-result-object v0
    if-eqz v0, :absent
    iget-object v0, p0, Ltv/plex/app/MainActivity;->questNavigationAnchor:Landroid/view/View;
    if-eqz v0, :absent
    invoke-virtual {v0}, Landroid/view/View;->isShown()Z
    move-result v1
    if-eqz v1, :absent
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/view/View;->setFocusableInTouchMode(Z)V
    invoke-virtual {v0}, Landroid/view/View;->clearFocus()V
    invoke-virtual {v0}, Landroid/view/View;->requestFocusFromTouch()Z
    move-result v0
    return v0
    :absent
    const/4 v0, 0x0
    return v0
.end method

.method private final questHandleNavigationTouch(Landroid/view/MotionEvent;)Z
    .locals 5

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getActionMasked()I
    move-result v0
    if-nez v0, :continuation
    const/4 v0, 0x0
    iput-boolean v0, p0, Ltv/plex/app/MainActivity;->questConsumeNavigationTouch:Z
    invoke-direct {p0, p1}, Ltv/plex/app/MainActivity;->questPointedNavigationItem(Landroid/view/MotionEvent;)Landroid/view/View;
    move-result-object v0
    if-eqz v0, :outside_check
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/view/View;->setFocusableInTouchMode(Z)V
    # Submenus also need native focus for Plex's TV selection callbacks. Keep
    # the top-level anchor for dismissal, and avoid refocusing an already
    # focused submenu item (which can recreate its child menu during a tap).
    invoke-virtual {v0}, Landroid/view/View;->getTag()Ljava/lang/Object;
    move-result-object v2
    instance-of v3, v2, Ljava/lang/String;
    if-eqz v3, :focus_item
    check-cast v2, Ljava/lang/String;
    const-string v3, "primary-navigation-"
    invoke-virtual {v2, v3}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v2
    if-eqz v2, :focus_item
    iput-object v0, p0, Ltv/plex/app/MainActivity;->questNavigationAnchor:Landroid/view/View;
    invoke-virtual {v0}, Landroid/view/View;->clearFocus()V
    :focus_item
    invoke-virtual {v0}, Landroid/view/View;->requestFocusFromTouch()Z
    goto :normal_touch

    :outside_check
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questNavigationModal()Landroid/view/View;
    move-result-object v0
    if-nez v0, :normal_touch
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questNavigationPopover()Landroid/view/View;
    move-result-object v0
    if-eqz v0, :normal_touch
    new-instance v1, Landroid/graphics/Rect;
    invoke-direct {v1}, Landroid/graphics/Rect;-><init>()V
    invoke-virtual {v0, v1}, Landroid/view/View;->getGlobalVisibleRect(Landroid/graphics/Rect;)Z
    move-result v0
    if-eqz v0, :normal_touch
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getRawX()F
    move-result v2
    float-to-int v2, v2
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getRawY()F
    move-result v3
    float-to-int v3, v3
    invoke-virtual {v1, v2, v3}, Landroid/graphics/Rect;->contains(II)Z
    move-result v0
    if-nez v0, :normal_touch
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questDismissNavigationPopover()Z
    move-result v0
    iput-boolean v0, p0, Ltv/plex/app/MainActivity;->questConsumeNavigationTouch:Z
    return v0

    :continuation
    iget-boolean v1, p0, Ltv/plex/app/MainActivity;->questConsumeNavigationTouch:Z
    if-eqz v1, :normal_touch
    const/4 v2, 0x1
    if-eq v0, v2, :clear
    const/4 v2, 0x3
    if-ne v0, v2, :consume
    :clear
    const/4 v0, 0x0
    iput-boolean v0, p0, Ltv/plex/app/MainActivity;->questConsumeNavigationTouch:Z
    :consume
    const/4 v0, 0x1
    return v0
    :normal_touch
    const/4 v0, 0x0
    return v0
.end method

.method private final questHandleNavigationBack(Landroid/view/KeyEvent;)Z
    .locals 3

    invoke-virtual {p1}, Landroid/view/KeyEvent;->getKeyCode()I
    move-result v0
    const/4 v1, 0x4
    if-ne v0, v1, :normal_key
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questNavigationModal()Landroid/view/View;
    move-result-object v0
    if-nez v0, :normal_key
    invoke-virtual {p1}, Landroid/view/KeyEvent;->getAction()I
    move-result v0
    iget-boolean v1, p0, Ltv/plex/app/MainActivity;->questConsumeNavigationBack:Z
    if-nez v0, :key_up
    if-nez v1, :consume
    invoke-direct {p0}, Ltv/plex/app/MainActivity;->questDismissNavigationPopover()Z
    move-result v0
    iput-boolean v0, p0, Ltv/plex/app/MainActivity;->questConsumeNavigationBack:Z
    return v0
    :key_up
    const/4 v2, 0x1
    if-ne v0, v2, :normal_key
    if-eqz v1, :normal_key
    const/4 v0, 0x0
    iput-boolean v0, p0, Ltv/plex/app/MainActivity;->questConsumeNavigationBack:Z
    :consume
    const/4 v0, 0x1
    return v0
    :normal_key
    const/4 v0, 0x0
    return v0
.end method
