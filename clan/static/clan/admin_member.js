'use strict';
(function ($) {
    $(document).ready(function () {

        var $userSelect = $('#id_user');
        if (!$userSelect.length) return;

        function fillFromProfile(userId) {
            if (!userId) return;

            fetch('/api/auth/user-info/?user_id=' + userId)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!data.ok) return;

                    var filled = [];

                    // Steam ник → поле "Никнейм"
                    var $nick = $('#id_nickname');
                    if ($nick.length && data.steam_name) {
                        $nick.val(data.steam_name);
                        highlight($nick);
                        filled.push('Ник: ' + data.steam_name);
                    }

                    // Роль → поле "Специализация"
                    var $spec = $('#id_specialization');
                    if ($spec.length && data.role && data.role !== 'any') {
                        $spec.val(data.role).trigger('change');
                        highlight($spec);
                        filled.push('Спец: ' + data.role);
                    }

                    // Часы → поле "Часов в Rust"
                    var $hours = $('#id_hours');
                    if ($hours.length && data.hours) {
                        $hours.val(data.hours);
                        highlight($hours);
                        filled.push('Часов: ' + data.hours);
                    }

                    if (filled.length) {
                        showInfo('✓ Данные подтянуты: ' + filled.join(' · '));
                    }
                })
                .catch(function () {
                    showInfo('⚠ Профиль не найден', true);
                });
        }

        function highlight($el) {
            $el.css({ 'background': '#162616', 'outline': '2px solid #5b8' });
            setTimeout(function () { $el.css({ 'background': '', 'outline': '' }); }, 2500);
        }

        function showInfo(msg, isWarn) {
            var $info = $('#wf-autofill-info');
            if (!$info.length) {
                $info = $('<p id="wf-autofill-info" style="' +
                    'padding:5px 10px;border-radius:3px;margin-top:6px;' +
                    'font-size:13px;font-weight:600;display:inline-block;' +
                    '"></p>');
                $userSelect.closest('.form-row, .field-user').append($info);
            }
            $info.text(msg).css({
                'color':      isWarn ? '#e98' : '#6c9',
                'background': isWarn ? 'rgba(200,80,80,.12)' : 'rgba(60,160,80,.12)',
                'border':     '1px solid ' + (isWarn ? '#e98' : '#6c9'),
            });
        }

        // Select2 event (Django admin autocomplete_fields использует Select2)
        $userSelect.on('select2:select', function (e) {
            fillFromProfile(e.params.data.id);
        });

        // Fallback: обычный change если Select2 не инициализирован
        $userSelect.on('change', function () {
            if (!$(this).hasClass('select2-hidden-accessible')) {
                fillFromProfile($(this).val());
            }
        });

    });
}(django.jQuery));
