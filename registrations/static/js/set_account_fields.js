const PRODUCT_MAPPING_FIELDS = [
    'name',
    'vat_code',
    'company_code',
    'main_ledger_account',
    'balance_profit_center',
    'internal_order',
    'profit_center',
    'project',
    'operation_area'
];

const accountFieldsEventListener = (event) => {
    if (event.type !== 'DOMContentLoaded'
        && !(event.target.tagName.toLowerCase() === 'a' && event.target.closest('#registration_account-group') !== null)) {
        return;
    }

    const accountSelect = document.querySelector('[id^="id_"][id$="-account"]');
    const accountFields = document.querySelectorAll(
        PRODUCT_MAPPING_FIELDS.map(field => `[id$="-${field}"]`).join(', ')
    );

    if (accountSelect !== null && accountFields.length > 0) {
        accountSelect.addEventListener('change', (event) => {
            const selectedOption = event.target.options[event.target.selectedIndex];
            accountFields.forEach(field => {
                field.value = selectedOption ? selectedOption.dataset[field.id.split('-')[2]] || '' : '';
            });
        });
    }
};

window.addEventListener('DOMContentLoaded', accountFieldsEventListener);
window.addEventListener('click', accountFieldsEventListener);
