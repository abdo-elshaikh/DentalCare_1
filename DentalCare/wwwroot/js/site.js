document.querySelectorAll('.password-toggle').forEach((button) => {
    button.addEventListener('click', () => {
        const input = button.parentElement.querySelector('input');
        const isHidden = input.type === 'password';
        input.type = isHidden ? 'text' : 'password';
        button.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');
        button.setAttribute('title', isHidden ? 'Hide password' : 'Show password');
        button.querySelector('i').className = isHidden ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
    });
});

