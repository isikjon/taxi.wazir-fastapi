$(document).ready(function () {
    const urlParams = new URLSearchParams(window.location.search);
    const phoneNumber = urlParams.get('phone');

    if (phoneNumber) {
        $('.active-phone-number').text(decodeURIComponent(phoneNumber));
    }

    const $smsInputs = $('.sms-code');

    $smsInputs.on('input', function (e) {
        const $this = $(this);

        this.value = this.value.replace(/[^\d]/g, '');

        if (this.value.length === 1) {
            $this.next('.sms-code').focus();
        }

        if ($smsInputs.last().is($this)) {
            validateCode();
        }
    });

    $smsInputs.on('keydown', function (e) {
        const $this = $(this);

        if (e.keyCode === 8 && !this.value) {
            $this.prev('.sms-code').focus();
        }
    });

    let timeLeft = 59;
    const timerElement = $('.timer-sms');
    const resendLink = $('.resend-sms');
    const invalidText = $('.invalid-text');
    const $form = $('.register__form form');

    resendLink.hide();
    invalidText.hide();

    function startTimer() {
        const timer = setInterval(function () {
            if (timeLeft <= 0) {
                clearInterval(timer);
                timerElement.hide();
                resendLink.show();
            } else {
                timerElement.text(`Код не пришел (0:${timeLeft.toString().padStart(2, '0')})`);
                timeLeft--;
            }
        }, 1000);
    }

    function validateCode() {
        const enteredCode = Array.from($smsInputs).map(input => input.value).join('');

        if (window.location.pathname.includes('survey/12.html')) {
            if (enteredCode === '1111') {
                $form.removeClass('invalid');
                invalidText.hide();
                resendLink.hide();
                window.location.href = '../profile/1.html';
            } else if (enteredCode.length === 4) {
                $form.addClass('invalid');
                invalidText.show();
                resendLink.show();
            }
        } else {
            if (enteredCode === '1111') {
                $form.removeClass('invalid');
                invalidText.hide();
                resendLink.hide();
                window.location.href = '3.html';
            } else if (enteredCode.length === 4) {
                $form.addClass('invalid');
                invalidText.show();
                resendLink.show();
            }
        }
    }

    resendLink.on('click', function (e) {
        e.preventDefault();
        timeLeft = 59;
        $(this).hide();
        timerElement.show();
        $form.removeClass('invalid');
        $smsInputs.val('');
        $smsInputs.first().focus();
        startTimer();
    });

    startTimer();

    $('.register__auth form input').on('input', function () {
        const $form = $('.register__auth form');
        const $inputs = $form.find('input');
        const $submitBtn = $form.find('.main__btn');

        const allFilled = Array.from($inputs).every(input => input.value.trim() !== '');

        if (allFilled) {
            $submitBtn.addClass('main__btn-active');
        } else {
            $submitBtn.removeClass('main__btn-active');
        }
    });

    $('.register__auth form').on('submit', function (e) {
        e.preventDefault();

        const $form = $(this);
        const $inputs = $form.find('input');
        const allFilled = Array.from($inputs).every(input => input.value.trim() !== '');

        if (allFilled) {
            window.location.href = '../survey/1.html';
        }
    });
});