// Auto-dismiss messages after 4s
document.addEventListener("DOMContentLoaded", function () {
    const alerts = document.querySelectorAll(".fade-out");
    setTimeout(() => {
      alerts.forEach(alert => {
        alert.classList.add("opacity-0");
        setTimeout(() => alert.remove(), 1000);
      });
    }, 4000);
  });