/**
 * Array Widget JavaScript
 * 
 * Provides dynamic add/remove functionality for ArrayAdminWidget
 */

/**
 * Add a new item to an array widget
 * @param {string} containerId - ID of the array widget container
 * @param {string} fieldName - Name of the field
 * @param {string} itemType - Type of input (text, number, email, url)
 */
function addArrayItem(containerId, fieldName, itemType) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const itemsContainer = container.querySelector('.array-items');
    if (!itemsContainer) return;
    
    // Check max rows limit
    const maxRows = container.dataset.maxRows;
    if (maxRows) {
        const currentCount = itemsContainer.querySelectorAll('.array-item').length;
        if (currentCount >= parseInt(maxRows)) {
            alert(`Maximum of ${maxRows} items allowed`);
            return;
        }
    }
    
    // Get current index
    const items = itemsContainer.querySelectorAll('.array-item');
    const newIndex = items.length;
    
    // Create new item
    const itemDiv = document.createElement('div');
    itemDiv.className = 'array-item';
    itemDiv.dataset.index = newIndex;
    itemDiv.innerHTML = `
        <input
            type="${itemType}"
            name="${fieldName}_item"
            value=""
            class="form-input array-input"
            data-array-item="true"
        />
        <button
            type="button"
            class="btn-remove-item"
            onclick="removeArrayItem(this)"
            title="Remove item"
        >
            <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
        </button>
    `;
    
    itemsContainer.appendChild(itemDiv);
    
    // Focus the new input
    const newInput = itemDiv.querySelector('input');
    if (newInput) {
        newInput.focus();
    }
    
    // Update hidden field
    updateArrayHiddenField(container, fieldName);
}

/**
 * Remove an item from an array widget
 * @param {HTMLElement} button - The remove button that was clicked
 */
function removeArrayItem(button) {
    const item = button.closest('.array-item');
    if (!item) return;
    
    const container = item.closest('.array-widget-container');
    if (!container) return;
    
    const itemsContainer = container.querySelector('.array-items');
    if (!itemsContainer) return;
    
    // Don't allow removing if only one item remains
    const items = itemsContainer.querySelectorAll('.array-item');
    if (items.length <= 1) {
        // Just clear the value instead
        const input = item.querySelector('input');
        if (input) {
            input.value = '';
        }
        return;
    }
    
    // Remove the item with animation
    item.style.opacity = '0';
    item.style.transform = 'translateX(-10px)';
    setTimeout(() => {
        item.remove();
        
        // Reindex remaining items
        const remainingItems = itemsContainer.querySelectorAll('.array-item');
        remainingItems.forEach((item, index) => {
            item.dataset.index = index;
        });
        
        // Update hidden field
        const fieldName = container.dataset.field;
        updateArrayHiddenField(container, fieldName);
    }, 200);
}

/**
 * Update the hidden field with current array values
 * @param {HTMLElement} container - The array widget container
 * @param {string} fieldName - Name of the field
 */
function updateArrayHiddenField(container, fieldName) {
    const inputs = container.querySelectorAll('.array-input');
    const values = Array.from(inputs)
        .map(input => input.value.trim())
        .filter(value => value !== ''); // Remove empty values
    
    const hiddenField = container.querySelector(`input[name="${fieldName}"]`);
    if (hiddenField) {
        hiddenField.value = JSON.stringify(values);
    }
}

/**
 * Initialize array widgets on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add change listeners to all array inputs
    const arrayContainers = document.querySelectorAll('.array-widget-container');
    
    arrayContainers.forEach(container => {
        const fieldName = container.dataset.field;
        const inputs = container.querySelectorAll('.array-input');
        
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                updateArrayHiddenField(container, fieldName);
            });
            
            // Add Enter key handler to add new item
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const itemType = container.dataset.itemType || 'text';
                    addArrayItem(container.id, fieldName, itemType);
                }
            });
        });
        
        // Initialize hidden field value
        updateArrayHiddenField(container, fieldName);
    });
});
