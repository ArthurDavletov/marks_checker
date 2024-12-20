const button = document.getElementById("form-submit")

button.addEventListener("click", () => {
    button.innerHTML = "Подождите немного...";
});

function disableButton() {
    button.disabled = true;
}