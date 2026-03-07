document.addEventListener("DOMContentLoaded", function () {

    const container = document.querySelector('.container');
    const registerBtn = document.querySelector('.register-btn');
    const loginBtn = document.querySelector('.login-btn');

    if (registerBtn) {
        registerBtn.addEventListener('click', function () {
            container.classList.add('active');
        });
    }

    if (loginBtn) {
        loginBtn.addEventListener('click', function () {
            container.classList.remove('active');
        });
    }
    const btn = document.getElementById("submitBtn");
        if (btn) {
        btn.addEventListener("click", () => {
        console.log("Clicked!");
    });

}

});
