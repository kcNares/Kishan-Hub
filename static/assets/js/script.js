// Kishan Hub Minimal JavaScript

// Import Bootstrap if needed
const bootstrap = window.bootstrap;

// Initialize page
document.addEventListener("DOMContentLoaded", () => {
  initializeReviewSystem();

  // Contact form submission
  const contactForm = document.querySelector(".contact-form form");
  if (contactForm) {
    contactForm.addEventListener("submit", function (e) {
      e.preventDefault();
      alert("Thank you for your message! We will get back to you soon.");
      this.reset();
    });
  }
});

// Star rating highlighting for reviews
function initializeReviewSystem() {
  const starRating = document.getElementById("starRating");
  const reviewForm = document.getElementById("reviewForm");

  if (starRating) {
    initializeStarRating();
  }

  if (reviewForm) {
    reviewForm.addEventListener("submit", handleReviewSubmission);
  }
}

function initializeStarRating() {
  const stars = document.querySelectorAll("#starRating i");
  const selectedRatingInput = document.getElementById("selectedRating");

  stars.forEach((star, index) => {
    star.addEventListener("mouseover", () => {
      highlightStars(index + 1);
    });
    star.addEventListener("mouseout", () => {
      const selectedRating = Number.parseInt(selectedRatingInput.value);
      highlightStars(selectedRating);
    });
    star.addEventListener("click", () => {
      const rating = index + 1;
      selectedRatingInput.value = rating;
      highlightStars(rating);
    });
  });
}

function highlightStars(rating) {
  const stars = document.querySelectorAll("#starRating i");
  stars.forEach((star, index) => {
    if (index < rating) {
      star.classList.remove("far");
      star.classList.add("fas");
    } else {
      star.classList.remove("fas");
      star.classList.add("far");
    }
  });
}

function handleReviewSubmission(e) {
  e.preventDefault();

  // In production, you'd submit the form with AJAX if desired
  alert("Thank you for your review!");
  e.target.reset();
  highlightStars(0);
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener("click", function (e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute("href"));
    if (target) {
      target.scrollIntoView({ behavior: "smooth" });
    }
  });
});

// Utility: Show a success message
function showSuccessMessage(message) {
  const alertDiv = document.createElement("div");
  alertDiv.className = "alert alert-success alert-dismissible fade show position-fixed";
  alertDiv.style.cssText = "top: 100px; right: 20px; z-index: 9999; min-width: 300px;";
  alertDiv.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  document.body.appendChild(alertDiv);
  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.remove();
    }
  }, 5000);
}

// search-tools
document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("searchInput");
  const autocompleteResults = document.getElementById("autocompleteResults");
  const searchBtn = document.getElementById("searchBtn");

  searchInput.addEventListener("input", function () {
    const query = this.value.trim();
    if (query.length === 0) {
      autocompleteResults.classList.add("d-none");
      return;
    }

    fetch(`/autocomplete/?q=${encodeURIComponent(query)}`)
      .then((response) => response.json())
      .then((data) => {
        autocompleteResults.innerHTML = "";
        if (data.length === 0) {
          autocompleteResults.classList.add("d-none");
        } else {
          data.forEach((item) => {
            const li = document.createElement("li");
            li.className = "list-group-item list-group-item-action";
            li.textContent = item;
            li.addEventListener("click", () => {
              searchInput.value = item;
              autocompleteResults.classList.add("d-none");
              performSearch(item);
            });
            autocompleteResults.appendChild(li);
          });
          autocompleteResults.classList.remove("d-none");
        }
      })
      .catch((error) => {
        console.error("Autocomplete error:", error);
      });
  });

  // Close suggestions when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-container")) {
      autocompleteResults.classList.add("d-none");
    }
  });

  // Search on Enter key
  searchInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      performSearch(this.value.trim());
    }
  });

  // Search on button click
  searchBtn.addEventListener("click", function (e) {
    e.preventDefault();
    performSearch(searchInput.value.trim());
  });

  function performSearch(query) {
    if (query.length > 0) {
      window.location.href = `/search/?q=${encodeURIComponent(query)}`;
    }
  }
});
