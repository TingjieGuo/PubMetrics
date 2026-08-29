// ==UserScript==
// @name         PubMed Journal Metrics
// @namespace    local
// @version      0.1
// @description  Show JIF and JCR quartile in PubMed search results and article pages
// @match        https://pubmed.ncbi.nlm.nih.gov/*
// @resource     journals https://raw.githubusercontent.com/TingjieGuo/journal-metrics/refs/heads/main/data/pubmed_metrics.json?token=GHSAT0AAAAAAEGEPI6HTHN73X3SSFDSVYKK2UTNE3Q
// @grant        GM_getResourceText
// ==/UserScript==

(function () {
  "use strict";

  // Step 1: Read the compact journal database from the external resource
  const journalText = GM_getResourceText("journals");

  // The compact database is already indexed by PubMed abbreviation
  const abbreviationIndex = JSON.parse(journalText);

  // ============================================================
  // Shared badge creation
  // ============================================================

  function createBadge(metrics, inline = false) {
    const badge = document.createElement("span");

    badge.className = "journal-metrics-badge";

    // Extract all quartiles
    //
    // Example:
    // ["Q1", "Q1", "Q2"]
    const quartiles = metrics.categories.map(
      (category) => category.quartile,
    );

    // Preserve duplicate quartiles
    //
    // Example:
    // ["Q1", "Q1", "Q2"] -> "Q1/Q1/Q2"
    const quartileText = quartiles.join("/");

    // Main badge text
    badge.textContent = `JIF ${metrics.jif}  |  ${quartileText}`;

    // Build the full category information shown on hover
    const categoryText = metrics.categories
      .map((category) => `${category.name}: ${category.quartile}`)
      .join("\n");

    const tooltipText = `JCR ${metrics.jcr_year}\n${categoryText}`;

    // Badge appearance
    badge.style.display = inline ? "inline-block" : "block";
    badge.style.width = "fit-content";

    if (inline) {
      badge.style.marginLeft = "8px";
      badge.style.marginRight = "4px";
      badge.style.verticalAlign = "baseline";
    } else {
      badge.style.marginTop = "5px";
      badge.style.marginBottom = "5px";
    }

    badge.style.fontWeight = "600";
    badge.style.padding = "2px 6px";
    badge.style.border = "1px solid #4D8055";
    badge.style.borderRadius = "6px";
    badge.style.position = "relative";

    // Create the custom tooltip
    const tooltip = document.createElement("span");

    tooltip.className = "journal-metrics-tooltip";
    tooltip.textContent = tooltipText;

    // Hide the tooltip by default
    tooltip.style.display = "none";

    // Make the tooltip float above the page content
    tooltip.style.position = "absolute";
    tooltip.style.zIndex = "9999";

    // Position the tooltip directly below the badge
    tooltip.style.left = "0";
    tooltip.style.top = "100%";
    tooltip.style.marginTop = "4px";

    // Tooltip appearance
    tooltip.style.padding = "6px 8px";
    tooltip.style.border = "1px solid #4D8055";
    tooltip.style.borderRadius = "6px";
    tooltip.style.background = "white";
    tooltip.style.fontWeight = "400";
    tooltip.style.whiteSpace = "pre";
    tooltip.style.width = "max-content";
    tooltip.style.maxWidth = "none";
    tooltip.style.boxShadow = "0 2px 6px rgba(0,0,0,0.15)";

    // Put the tooltip inside the badge
    badge.appendChild(tooltip);

    // Show immediately when the mouse enters the badge
    badge.addEventListener("mouseenter", () => {
      tooltip.style.display = "block";
    });

    // Hide immediately when the mouse leaves the badge
    badge.addEventListener("mouseleave", () => {
      tooltip.style.display = "none";
    });

    return badge;
  }

  // ============================================================
  // Search results page
  // ============================================================

  function processResults() {
    const results = document.querySelectorAll(".docsum-content");

    results.forEach((result) => {
      // Find the journal citation element
      const citation = result.querySelector(".docsum-journal-citation");

      if (!citation) {
        return;
      }

      // Avoid adding the badge more than once
      if (result.querySelector(".journal-metrics-badge")) {
        return;
      }

      // Example:
      // "Clin Pharmacokinet. 2025 Aug;64(8):..."
      const citationText = citation.textContent.trim();

      // Extract the PubMed journal abbreviation
      const firstPeriodPosition = citationText.indexOf(".");

      if (firstPeriodPosition === -1) {
        return;
      }

      const pubmedAbbreviation = citationText
        .slice(0, firstPeriodPosition)
        .trim();

      // Look up the journal directly in the compact database
      const metrics = abbreviationIndex[pubmedAbbreviation];

      // No matching journal in our database
      if (!metrics) {
        return;
      }

      // Create the badge
      const badge = createBadge(metrics, false);

      // Insert the badge on its own line
      // immediately after the journal citation
      citation.insertAdjacentElement("afterend", badge);
    });
  }

  // ============================================================
  // Individual article page
  // ============================================================

  function processArticlePage() {
    // Only continue if this is an individual article page
    const articlePage = document.querySelector("#article-page");

    if (!articlePage) {
      return;
    }

    // Avoid adding the badge more than once
    if (document.querySelector(".journal-metrics-article-badge")) {
      return;
    }

    // Find the journal container in the main desktop citation
    const journalActions = document.querySelector(
      "#full-view-heading .journal-actions",
    );

    if (!journalActions) {
      return;
    }

    // Find the journal name button
    const journalButton = journalActions.querySelector(
      ".journal-actions-trigger",
    );

    if (!journalButton) {
      return;
    }

    // The button text is the PubMed/NLM journal abbreviation
    //
    // Example:
    // "J Pharmacokinet Pharmacodyn"
    const pubmedAbbreviation = journalButton.textContent.trim();

    // Look up the journal directly in the compact database
    const metrics = abbreviationIndex[pubmedAbbreviation];

    if (!metrics) {
      return;
    }

    // Create an inline badge
    const badge = createBadge(metrics, true);

    badge.classList.add("journal-metrics-article-badge");

    // Slightly tighter appearance on article pages
    badge.style.padding = "1px 5px";

    // Insert the badge after the entire journal-actions container,
    // but before PubMed's period and citation date.
    journalActions.insertAdjacentElement("afterend", badge);
  }

  // ============================================================
  // Initial processing
  // ============================================================

  processResults();
  processArticlePage();

  // ============================================================
  // Watch for dynamically added PubMed content
  // ============================================================

  const observer = new MutationObserver(() => {
    processResults();
    processArticlePage();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
})();