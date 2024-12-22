"use strict";

function deleteAllCookies() {
    document.cookie.split(';').forEach(cookie => {
        const eqPos = cookie.indexOf('=');
        const name = eqPos > -1 ? cookie.substring(0, eqPos) : cookie;
        document.cookie = name + '=;expires=Thu, 01 Jan 1970 00:00:00 GMT';
    });
}

let button = document.getElementById("logout-button");

button.addEventListener("click", () => {
    deleteAllCookies();
    window.location.replace("/");
});

let reload_button = document.getElementById("reload-button");

reload_button.addEventListener("click", () => {
    window.location.reload();
});

let buttons = document.getElementsByClassName("filters")

for (let input_button of buttons) {
    input_button.onchange = () => {
        let cells = document.getElementsByClassName(input_button.name);
        for (let cell of cells) {
            cell.toggleAttribute("hidden");
        }
    };
}