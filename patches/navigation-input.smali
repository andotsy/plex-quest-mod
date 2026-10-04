# Pointer-to-TV focus integration for the top navigation popover.
.field private questNavigationAnchor:Landroid/view/View;
.field private questConsumeNavigationTouch:Z
.field private questConsumeNavigationBack:Z

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
    invoke-virtual {v0}, Landroid/view/View;->isShown()Z
    move-result v1
    if-eqz v1, :absent
    invoke-virtual {v0}, Landroid/view/View;->getAlpha()F
    move-result v1
    const/high16 v2, 0x3f000000
    cmpg-float v1, v1, v2
    if-ltz v1, :absent
    invoke-virtual {v0}, Landroid/view/View;->getWidth()I
    move-result v1
    if-lez v1, :absent
    return-object v0
    :absent
    const/4 v0, 0x0
    return-object v0
.end method

.method private final questPointedNavigationItem(Landroid/view/MotionEvent;)Landroid/view/View;
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
    instance-of v2, v1, Ljava/lang/String;
    if-eqz v2, :next
    check-cast v1, Ljava/lang/String;
    const-string v2, "primary-navigation-"
    invoke-virtual {v1, v2}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v1
    if-eqz v1, :next
    invoke-virtual {v0}, Landroid/view/View;->isClickable()Z
    move-result v1
    if-nez v1, :found
    :next
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
    iput-object v0, p0, Ltv/plex/app/MainActivity;->questNavigationAnchor:Landroid/view/View;
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/view/View;->setFocusableInTouchMode(Z)V
    invoke-virtual {v0}, Landroid/view/View;->clearFocus()V
    invoke-virtual {v0}, Landroid/view/View;->requestFocusFromTouch()Z
    goto :normal_touch

    :outside_check
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
