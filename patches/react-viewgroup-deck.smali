# Expose the deck's existing four-way focus trap for native input routing.
.method public final questTrapsAllFocusDirections()Z
    .locals 1

    iget-boolean v0, p0, Lcom/facebook/react/views/view/ReactViewGroup;->trapFocusUp:Z
    if-eqz v0, :absent
    iget-boolean v0, p0, Lcom/facebook/react/views/view/ReactViewGroup;->trapFocusDown:Z
    if-eqz v0, :absent
    iget-boolean v0, p0, Lcom/facebook/react/views/view/ReactViewGroup;->trapFocusLeft:Z
    if-eqz v0, :absent
    iget-boolean v0, p0, Lcom/facebook/react/views/view/ReactViewGroup;->trapFocusRight:Z
    if-eqz v0, :absent
    const/4 v0, 0x1
    return v0
    :absent
    const/4 v0, 0x0
    return v0
.end method
