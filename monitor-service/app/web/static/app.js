(function () {
    const REFRESH_KEY = "monitor.autoRefresh";
    const REFRESH_INTERVAL_MS = 15000;
    const checkbox = document.getElementById("auto-refresh");

    if (checkbox) {
        let timer = null;

        const start = () => {
            timer = window.setTimeout(() => window.location.reload(), REFRESH_INTERVAL_MS);
        };
        const stop = () => {
            if (timer !== null) {
                window.clearTimeout(timer);
                timer = null;
            }
        };

        checkbox.checked = window.localStorage.getItem(REFRESH_KEY) === "1";
        if (checkbox.checked) {
            start();
        }

        checkbox.addEventListener("change", () => {
            window.localStorage.setItem(REFRESH_KEY, checkbox.checked ? "1" : "0");
            if (checkbox.checked) {
                start();
            } else {
                stop();
            }
        });
    }

    document.querySelectorAll("[data-confirm]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!window.confirm(form.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll("[data-copy-target]").forEach((button) => {
        button.addEventListener("click", async () => {
            const target = document.getElementById(button.dataset.copyTarget);
            if (!target) {
                return;
            }

            try {
                await navigator.clipboard.writeText(target.textContent);
                const original = button.textContent;
                button.textContent = "Скопировано";
                window.setTimeout(() => {
                    button.textContent = original;
                }, 1500);
            } catch (error) {
                console.warn("clipboard write failed", error);
            }
        });
    });

    document.querySelectorAll("[data-autosubmit]").forEach((field) => {
        field.addEventListener("change", () => field.form.submit());
    });
})();
