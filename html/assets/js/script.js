let menu = $(".menu")
let settings = $(".settings")
let support = $(".support")
menu.on("click", function () {
    $(".navbar__menu-info").toggleClass("navbar__menu-info-active");
});
settings.on("click", function () {
    $(".navbar__menu-settings").toggleClass("navbar__menu-settings-active");
});
support.on("click", function () {
    $(".navbar__settings").toggleClass("navbar__menu-settings-active");
});
$(document).keydown(function (event) {
    if (event.key === 'F2') {
        window.location.href = 'https://wazir.kg/disp/new_order.html';
    }
});
