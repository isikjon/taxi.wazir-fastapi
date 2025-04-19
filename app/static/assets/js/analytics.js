// analytics.js - Скрипт для страницы аналитики
document.addEventListener('DOMContentLoaded', function () {
    // Инициализация градиентов для диаграмм
    initDonutCharts();

    // Добавляем эффекты при наведении на диаграммы
    setupHoverEffects();
});

/**
 * Инициализирует круговые диаграммы с анимацией
 */
function initDonutCharts() {
    // Настройка градиента и анимация первой диаграммы для водителей
    const donut1 = document.querySelector('.donut-1');
    if (donut1) {
        // Создаем красивый градиент для диаграммы водителей
        donut1.style.background = `conic-gradient(
            #1E6BC7 0% 100%, 
            transparent 100% 100%
        )`;

        // Добавляем анимацию появления
        animateDonut(donut1, 100);
    }

    // Настройка градиента и анимация второй диаграммы для машин
    const donut2 = document.querySelector('.donut-2');
    if (donut2) {
        // Создаем красивый градиент для диаграммы машин
        donut2.style.background = `conic-gradient(
            #2A9D8F 0% 100%, 
            transparent 100% 100%
        )`;

        // Добавляем анимацию появления
        animateDonut(donut2, 100);
    }

    // Настройка градиента и анимация третьей диаграммы для категорий заказов
    const donut3 = document.querySelector('.donut-3');
    if (donut3) {
        // Создаем красивый градиент для диаграммы категорий
        donut3.style.background = `conic-gradient(
            #8D6E63 0% 95%, 
            #009688 95% 100%
        )`;

        // Добавляем анимацию появления
        animateDonut(donut3, 95, 5);
    }
}

/**
 * Анимирует появление круговой диаграммы
 * @param {HTMLElement} donutElement - Элемент диаграммы
 * @param {number} mainPercent - Процент основного цвета
 * @param {number} secondPercent - Процент второго цвета (по умолчанию 0)
 */
function animateDonut(donutElement, mainPercent, secondPercent = 0) {
    // Начальное значение для анимации
    let currentPercent = 0;

    // Получаем стиль фона
    const background = donutElement.style.background;

    // Определяем цвета из исходного градиента
    const colors = background.match(/#[a-fA-F0-9]{6}/g);
    const mainColor = colors[0];
    const secondColor = colors.length > 1 ? colors[1] : 'transparent';

    // Интервал для анимации
    const animInterval = setInterval(() => {
        currentPercent += 3;

        if (currentPercent >= mainPercent) {
            currentPercent = mainPercent;
            clearInterval(animInterval);
        }

        // Создаем новый градиент с текущим процентом
        if (secondPercent > 0) {
            donutElement.style.background = `conic-gradient(
                ${mainColor} 0% ${currentPercent}%, 
                ${secondColor} ${currentPercent}% 100%
            )`;
        } else {
            donutElement.style.background = `conic-gradient(
                ${mainColor} 0% ${currentPercent}%, 
                transparent ${currentPercent}% 100%
            )`;
        }
    }, 20);
}

/**
 * Настройка эффектов при наведении на элементы диаграмм
 */
function setupHoverEffects() {
    // Добавляем эффекты при наведении на блоки с диаграммами
    const chartBlocks = document.querySelectorAll('.chart-block');

    chartBlocks.forEach(block => {
        block.addEventListener('mouseenter', function () {
            // Увеличиваем размер текста в центре диаграммы
            const centerText = this.querySelector('.donut-center-text');
            if (centerText) {
                centerText.style.fontSize = '42px';
                centerText.style.transition = 'font-size 0.3s ease';
            }

            // Добавляем яркое свечение для диаграммы
            const donut = this.querySelector('.donut-chart');
            if (donut) {
                donut.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.3), inset 0 0 20px rgba(255, 255, 255, 0.15)';
                donut.style.transition = 'box-shadow 0.3s ease';
            }
        });

        block.addEventListener('mouseleave', function () {
            // Возвращаем исходный размер текста
            const centerText = this.querySelector('.donut-center-text');
            if (centerText) {
                centerText.style.fontSize = '36px';
            }

            // Возвращаем исходное свечение
            const donut = this.querySelector('.donut-chart');
            if (donut) {
                donut.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.2), inset 0 0 15px rgba(0, 0, 0, 0.3)';
            }
        });
    });
}

/**
 * Обновляет круговую диаграмму, устанавливая CSS-переменную с процентом
 * @param {string} elementId - ID элемента доната
 * @param {number} percentage - Значение процента
 * @param {string} cssVarName - Имя CSS-переменной
 */
function updateDonutChart(elementId, percentage, cssVarName) {
    const donutElement = document.getElementById(elementId);
    if (donutElement) {
        donutElement.style.setProperty(`--${cssVarName}`, `${percentage}%`);
    }
}

/**
 * Обновляет текст в центре доната
 * @param {string} elementId - ID элемента с текстом
 * @param {number} percentage - Значение процента
 */
function updateCenterText(elementId, percentage) {
    const textElement = document.getElementById(elementId);
    if (textElement) {
        textElement.textContent = `${percentage}%`;
    }
}

/**
 * Обновляет значения в легенде
 * @param {string} elementId - ID элемента легенды
 * @param {number} value - Значение процента
 */
function updateLegendValues(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = `${value}%`;
    }
} 