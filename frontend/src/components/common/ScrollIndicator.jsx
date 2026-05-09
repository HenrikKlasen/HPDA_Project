import React, { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Scroll indicator component that shows a hint when there's more content below.
 * Once dismissed in a specific tab (by scrolling), it will never reappear in that same tab.
 */
function ScrollIndicator() {
  const location = useLocation();
  const [showIndicator, setShowIndicator] = useState(false);

  // Create a unique storage key for each page/tab
  const storageKey = `hpda_scroll_hint_dismissed_${location.pathname}`;

  useEffect(() => {
    // Reset state when switching tabs
    const isDismissed = localStorage.getItem(storageKey) === "true";
    if (isDismissed) {
      setShowIndicator(false);
      return;
    }

    const checkScroll = () => {
      // Check if already dismissed in this tab
      if (localStorage.getItem(storageKey) === "true") {
        setShowIndicator(false);
        return;
      }

      // Show indicator if page is scrollable and user hasn't scrolled much yet
      const isScrollable =
        document.documentElement.scrollHeight > window.innerHeight;
      const hasScrolled = window.scrollY > 50;
      const isNearBottom =
        window.innerHeight + window.scrollY >=
        document.documentElement.scrollHeight - 100;

      const shouldShow = isScrollable && !hasScrolled && !isNearBottom;

      // If the user has scrolled significantly, mark as dismissed for this specific tab forever
      if (hasScrolled) {
        localStorage.setItem(storageKey, "true");
        setShowIndicator(false);
      } else {
        setShowIndicator(shouldShow);
      }
    };

    // Check on mount and on scroll/resize
    checkScroll();
    window.addEventListener("scroll", checkScroll);
    window.addEventListener("resize", checkScroll);

    return () => {
      window.removeEventListener("scroll", checkScroll);
      window.removeEventListener("resize", checkScroll);
    };
  }, [location.pathname, storageKey]);

  if (!showIndicator) return null;

  return (
    <div className="scroll-hint">
      <span className="scroll-hint-icon">↓</span>
      <span>Scroll for more insights</span>
    </div>
  );
}

export default ScrollIndicator;
