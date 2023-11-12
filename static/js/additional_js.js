const accessTypeRadios = document.querySelectorAll('input[name="accessType"]');
const cameraDropdown = document.getElementById('cameraDropdown');

accessTypeRadios.forEach(radio => {
    radio.addEventListener('change', function () {
        if (this.value === 'chooseCamera') {
            cameraDropdown.classList.remove('hidden');
        } else {
            cameraDropdown.classList.add('hidden');
        }
    });
});