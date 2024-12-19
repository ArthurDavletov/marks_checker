const button = document.getElementById("form-submit")

button.addEventListener("click", () => {
    button.innerHTML = "Подождите немного...";
    // button.disabled = true;
});

function disableButton() {
    button.disabled = true;
}