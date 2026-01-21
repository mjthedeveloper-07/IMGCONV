const enhanceButton = document.getElementById("enhanceButton");
const enhanceResult = document.getElementById("enhanceResult");
const promptField = document.getElementById("prompt");
const formatField = document.getElementById("format");
const qualityField = document.getElementById("quality");

if (enhanceButton) {
  enhanceButton.addEventListener("click", async () => {
    const prompt = promptField ? promptField.value.trim() : "";
    if (!prompt) {
      enhanceResult.textContent = "Add a prompt to get recommendations.";
      enhanceResult.classList.remove("hidden");
      return;
    }
    enhanceButton.disabled = true;
    enhanceButton.textContent = "Enhancing...";
    try {
      const response = await fetch("/prompt-enhance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}.`);
      }
      const data = await response.json();
      if (data.format && formatField) {
        formatField.value = data.format;
      }
      if (qualityField && data.quality) {
        qualityField.value = data.quality;
      }
      enhanceResult.textContent = `${data.format} · Quality ${data.quality} — ${data.reason}`;
      enhanceResult.classList.remove("hidden");
    } catch (error) {
      const errorMessage =
        (error && error.message) || "Network error while enhancing prompt.";
      enhanceResult.textContent = errorMessage;
      enhanceResult.classList.remove("hidden");
    } finally {
      enhanceButton.disabled = false;
      enhanceButton.textContent = "Enhance Prompt";
    }
  });
}
