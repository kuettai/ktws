// Click a Mermaid diagram to view it full screen (Esc or click again to close).
document$.subscribe(() => {
  document.querySelectorAll(".mermaid").forEach((el) => {
    if (el.dataset.zoom) return;
    el.dataset.zoom = "1";
    el.title = "Click to view full screen";
    el.addEventListener("click", () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (el.requestFullscreen) el.requestFullscreen();
    });
  });
});

// "Open full size" diagram links (PNG / SVG) open in a new tab.
document$.subscribe(() => {
  document.querySelectorAll('a[href*="img/diagrams/"]').forEach((a) => {
    a.target = "_blank";
    a.rel = "noopener";
  });
});
