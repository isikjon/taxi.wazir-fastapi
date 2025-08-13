let menu = $(".menu")
let settings = $(".settings")
let support = $(".support")

// Функция для закрытия всех меню
function closeAllMenus() {
    $(".navbar__menu-info").removeClass("navbar__menu-info-active");
    $(".navbar__menu-settings").removeClass("navbar__menu-settings-active");
    $(".navbar__settings").removeClass("navbar__menu-settings-active");
}

// Эксклюзивное открытие меню "Информация"
menu.on("click", function (e) {
    e.preventDefault();
    const isCurrentlyOpen = $(".navbar__menu-info").hasClass("navbar__menu-info-active");
    
    // Закрываем все меню
    closeAllMenus();
    
    // Если текущее меню было закрыто, открываем его
    if (!isCurrentlyOpen) {
        $(".navbar__menu-info").addClass("navbar__menu-info-active");
    }
});

// Эксклюзивное открытие меню "Настройки"
settings.on("click", function (e) {
    e.preventDefault();
    const isCurrentlyOpen = $(".navbar__menu-settings").hasClass("navbar__menu-settings-active");
    
    // Закрываем все меню
    closeAllMenus();
    
    // Если текущее меню было закрыто, открываем его
    if (!isCurrentlyOpen) {
        $(".navbar__menu-settings").addClass("navbar__menu-settings-active");
    }
});

// Эксклюзивное открытие меню "Поддержка"  
support.on("click", function (e) {
    e.preventDefault();
    const isCurrentlyOpen = $(".navbar__settings").hasClass("navbar__menu-settings-active");
    
    // Закрываем все меню
    closeAllMenus();
    
    // Если текущее меню было закрыто, открываем его
    if (!isCurrentlyOpen) {
        $(".navbar__settings").addClass("navbar__menu-settings-active");
    }
});

// Закрытие меню при клике вне их области
$(document).on("click", function (e) {
    const isMenuButton = $(e.target).closest(".menu, .settings, .support").length > 0;
    const isMenuContent = $(e.target).closest(".navbar__menu").length > 0;
    
    if (!isMenuButton && !isMenuContent) {
        closeAllMenus();
    }
});
$(document).keydown(function (event) {
    if (event.key === 'F2') {
        window.location.href = '/disp/new_order';
    }
});
