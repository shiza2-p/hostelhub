document.addEventListener("DOMContentLoaded", function () {

  const fadeEls = document.querySelectorAll(".fade-up");
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          setTimeout(() => entry.target.classList.add("visible"), i * 80);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  fadeEls.forEach((el) => observer.observe(el));

  const navLinks = document.querySelectorAll(".navbar-nav .nav-link");
  const currentPage = location.pathname.split("/").pop() || "index.html";
  navLinks.forEach((link) => {
    if (link.getAttribute("href") === currentPage) {
      link.classList.add("active");
    }
  });

  function animateCounter(el) {
    const target = parseInt(el.dataset.target, 10);
    const duration = 1600;
    const step = target / (duration / 16);
    let current = 0;
    const timer = setInterval(() => {
      current += step;
      if (current >= target) { current = target; clearInterval(timer); }
      el.textContent = Math.floor(current) + (el.dataset.suffix || "");
    }, 16);
  }
  const counters = document.querySelectorAll(".counter");
  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        counterObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.4 });
  counters.forEach((c) => counterObserver.observe(c));

  const filterBtns = document.querySelectorAll(".room-filter-btn");
  const roomCards  = document.querySelectorAll(".room-card");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", function () {
      filterBtns.forEach((b) => b.classList.remove("active"));
      this.classList.add("active");
      const filter = this.dataset.filter;
      roomCards.forEach((card) => {
        const show = filter === "all" || card.dataset.type === filter;
        card.style.display = show ? "" : "none";
      });
    });
  });

  const forms = document.querySelectorAll(".needs-validate");
  forms.forEach((form) => {
    form.addEventListener("submit", function (e) {
      if (!form.checkValidity()) {
        e.preventDefault();
        e.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });

});
