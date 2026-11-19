const planner = document.querySelector("#planner");
const activity = document.querySelector("#activity");
const locationInput = document.querySelector("#location");
const time = document.querySelector("#time");
const resultsSection = document.querySelector("#conditions");
const resultGrid = document.querySelector("#result-grid");
const resultsSummary = document.querySelector("#results-summary");
const locateButton = document.querySelector("#locate-button");

const previewWindows = [
  {
    label: "Best match",
    title: "Morning window",
    detail: "Calmer winds and favorable water conditions make this the strongest preview window.",
    conditions: ["7–10 AM", "Light wind", "Good visibility"],
  },
  {
    label: "Good alternative",
    title: "Late afternoon",
    detail: "Conditions may improve again later, with a little more variability than the top pick.",
    conditions: ["4–6 PM", "Moderate wind", "Rising tide"],
  },
  {
    label: "Worth watching",
    title: "Next-day outlook",
    detail: "A promising backup window that should be rechecked as newer observations arrive.",
    conditions: ["Tomorrow", "Forecast", "Medium confidence"],
  },
];

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderPreviewResults() {
  const place = locationInput.value.trim();
  const selectedActivity = activity.options[activity.selectedIndex].text;
  const selectedTime = time.options[time.selectedIndex].text.toLowerCase();

  resultsSummary.textContent = `${selectedActivity} near ${place} · ${selectedTime}`;
  resultGrid.replaceChildren(
    ...previewWindows.map((window) => {
      const card = document.createElement("article");
      card.className = "result-card";

      const rank = document.createElement("span");
      rank.className = "result-rank";
      rank.textContent = window.label;

      const heading = document.createElement("h3");
      heading.textContent = window.title;

      const detail = document.createElement("p");
      detail.textContent = window.detail;

      const list = document.createElement("ul");
      list.className = "condition-list";
      window.conditions.forEach((condition) => {
        const item = document.createElement("li");
        item.textContent = condition;
        list.append(item);
      });

      card.append(rank, heading, detail, list);
      return card;
    }),
  );

  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

planner.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!planner.reportValidity()) return;
  renderPreviewResults();
});

locateButton.addEventListener("click", () => {
  if (!navigator.geolocation) {
    locationInput.placeholder = "Location unavailable — enter a place";
    locationInput.focus();
    return;
  }

  locateButton.disabled = true;
  locateButton.textContent = "…";
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      locationInput.value = `${coords.latitude.toFixed(3)}, ${coords.longitude.toFixed(3)}`;
      locateButton.disabled = false;
      locateButton.textContent = "◎";
    },
    () => {
      locationInput.placeholder = "Permission denied — enter a place";
      locateButton.disabled = false;
      locateButton.textContent = "◎";
      locationInput.focus();
    },
    { enableHighAccuracy: false, timeout: 8000 },
  );
});

document.title = `Tidewise — ${titleCase(activity.value)} conditions`;
activity.addEventListener("change", () => {
  document.title = `Tidewise — ${titleCase(activity.value)} conditions`;
});
