document.addEventListener("DOMContentLoaded", () => {
  // 1. Toast xabarlari (4 soniyadan so'ng avtomatik yoki x bosilganda yopiladi)
  document.querySelectorAll(".toast").forEach((toast) => {
    const closeBtn = toast.querySelector(".toast-close") || toast.querySelector("button");
    const close = () => {
      toast.classList.add("hide");
      setTimeout(() => toast.remove(), 400);
    };
    const timer = setTimeout(close, 4000);
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        clearTimeout(timer);
        close();
      });
    }
  });

  // 2. Profil menyusi (Dropdown)
  const pbtn = document.getElementById("pbtn");
  const menu = document.getElementById("menu");
  if (pbtn && menu) {
    const setOpen = (open) => {
      menu.classList.toggle("open", open);
      pbtn.setAttribute("aria-expanded", open ? "true" : "false");
    };

    pbtn.addEventListener("click", (e) => {
      e.stopPropagation();
      setOpen(!menu.classList.contains("open"));
    });

    document.addEventListener("click", (e) => {
      if (!menu.contains(e.target) && !pbtn.contains(e.target)) {
        setOpen(false);
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        setOpen(false);
        pbtn.focus();
      }
    });
  }

  // 3. Mavzuni almashtirish (Dark/Light mode)
  const themeToggle = document.getElementById("themeToggle");
  const currentTheme = localStorage.getItem("smarthelp-theme");
  if (currentTheme) {
    document.documentElement.setAttribute("data-theme", currentTheme);
  }
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const active = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", active);
      localStorage.setItem("smarthelp-theme", active);
    });
  }

  // 4. Modallarni boshqarish (Xona va qurilma qo'shish/tahrirlash)
  window.openModal = function(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.add("active");
  };

  window.closeModal = function(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.remove("active");
  };

  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) {
        backdrop.classList.remove("active");
      }
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-backdrop.active").forEach((m) => m.classList.remove("active"));
    }
  });
});
