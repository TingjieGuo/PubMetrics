// ==UserScript==
// @name         PubMed Journal Metrics
// @namespace    local
// @version      0.2
// @description  Show JIF and JCR quartile in PubMed search results
// @match        https://pubmed.ncbi.nlm.nih.gov/*
// @resource     journals https://raw.githubusercontent.com/TingjieGuo/journal-metrics/refs/heads/main/data/pubmed_metrics.json
// @grant        GM_getResourceText
// ==/UserScript==

(function () {
  "use strict";

  // Step 1: Read the compact journal database from the external resource
  const journalText = GM_getResourceText("journals");

  // The compact database is already indexed by PubMed abbreviation
  const abbreviationIndex = JSON.parse(journalText);

  // Step 2: Find all PubMed search results on the page
  const results = document.querySelectorAll(".docsum-content");

  // Step 3: Process each search result
  results.forEach((result) => {
    // Step 4: Find the journal citation element
    const citation = result.querySelector(".docsum-journal-citation");

    // Some PubMed page layouts may not contain this element
    if (!citation) {
      return;
    }

    // Avoid adding the badge more than once
    if (result.querySelector(".journal-metrics-badge")) {
      return;
    }

    // Step 5: Read the citation text
    //
    // Example:
    // "Clin Pharmacokinet. 2025 Aug;64(8):..."
    const citationText = citation.textContent.trim();

    // Step 6: Extract the PubMed journal abbreviation
    //
    // The journal abbreviation appears at the beginning of the citation
    // and is followed by a period.
    const firstPeriodPosition = citationText.indexOf(".");

    if (firstPeriodPosition === -1) {
      return;
    }

    const pubmedAbbreviation = citationText
      .slice(0, firstPeriodPosition)
      .trim();

    // Step 7: Look up the journal directly in the compact database
    const metrics = abbreviationIndex[pubmedAbbreviation];

    // No matching journal in our database
    if (!metrics) {
      return;
    }

    // Step 8: Create the JIF / quartile badge
    const badge = document.createElement("span");

    badge.className = "journal-metrics-badge";

    // Extract all quartiles
    //
    // Example:
    // ["Q1", "Q1", "Q2"]
    const quartiles = metrics.categories.map((category) => category.quartile);

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
    badge.style.display = "block";
    badge.style.width = "fit-content";
    badge.style.marginTop = "5px";
    badge.style.marginBottom = "5px";

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

    // Step 9: Insert the badge on its own line
    // immediately after the journal citation
    citation.insertAdjacentElement("afterend", badge);
  });
})();