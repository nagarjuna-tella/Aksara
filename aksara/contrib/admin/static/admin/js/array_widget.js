/**
 * Array Widget JavaScript
 * Version: 0.5.9
 * 
 * Provides dynamic add/remove functionality for ArrayAdminWidget
 * Features:
 * - Add/remove items dynamically
 * - Drag-and-drop reordering
 * - Keyboard navigation (Enter to add, Tab to navigate)
 * - Max items limit
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
            showArrayMessage(container, `Maximum of ${maxRows} items allowed`, 'warning');
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
    itemDiv.draggable = true;
    itemDiv.innerHTML = `
        <span class="array-drag-handle" title="Drag to reorder">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/>
                <circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/>
            </svg>
        </span>
        <input
            type="${itemType}"
            name="${fieldName}_item"
            value=""
            class="form-input array-input"
            data-array-item="true"
            placeholder="Enter value..."
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
    
    // Add drag event listeners
    addDragListeners(itemDiv, container, fieldName);
    
    // Add input event listener
    const newInput = itemDiv.querySelector('input');
    if (newInput) {
        newInput.addEventListener('input', function() {
            updateArrayHiddenField(container, fieldName);
        });
        
        newInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                addArrayItem(container.id, fieldName, itemType);
            }
        });
        
        // Focus the new input
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
            input.focus();
        }
        const fieldName = container.dataset.field;
        updateArrayHiddenField(container, fieldName);
        return;
    }
    
    // Remove the item with animation
    item.style.opacity = '0';
    item.style.transform = 'translateX(-10px)';
    item.style.height = item.offsetHeight + 'px';
    
    setTimeout(() => {
        item.style.height = '0';
        item.style.margin = '0';
        item.style.padding = '0';
        
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
        }, 150);
    }, 150);
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
    
    // Update count badge if present
    const countBadge = container.querySelector('.array-count');
    if (countBadge) {
        countBadge.textContent = `${values.length} item${values.length !== 1 ? 's' : ''}`;
    }
}

/**
 * Show a temporary message in the array widget
 */
function showArrayMessage(container, message, type) {
    let msgDiv = container.querySelector('.array-message');
    if (!msgDiv) {
        msgDiv = document.createElement('div');
        msgDiv.className = 'array-message';
        container.appendChild(msgDiv);
    }
    
    msgDiv.textContent = message;
    msgDiv.className = `array-message array-message-${type}`;
    msgDiv.style.display = 'block';
    
    setTimeout(() => {
        msgDiv.style.display = 'none';
    }, 2000);
}

/**
 * Add drag event listeners to an item
 */
function addDragListeners(item, container, fieldName) {
    const handle = item.querySelector('.array-drag-handle');
    
    handle.addEventListener('mousedown', () => {
        item.draggable = true;
    });
    
    item.addEventListener('dragstart', function(e) {
        item.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
    });
    
    item.addEventListener('dragend', function() {
        item.classList.remove('dragging');
        updateArrayHiddenField(container, fieldName);
    });
    
    item.addEventListener('dragover', function(e) {
        e.preventDefault();
        const dragging = container.querySelector('.dragging');
        if (dragging && dragging !== item) {
            const rect = item.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            const parent = item.parentNode;
            
            if (e.clientY < midY) {
                parent.insertBefore(dragging, item);
            } else {
                parent.insertBefore(dragging, item.nextSibling);
            }
        }
    });
}

/**
 * Initialize array widgets on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all array containers
    const arrayContainers = document.querySelectorAll('.array-widget-container');
    
    arrayContainers.forEach(container => {
        const fieldName = container.dataset.field;
        const items = container.querySelectorAll('.array-item');
        
        items.forEach(item => {
            const input = item.querySelector('.array-input');
            
            if (input) {
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
            }
            
            // Add drag listeners
            addDragListeners(item, container, fieldName);
        });
        
        // Initialize hidden field value
        updateArrayHiddenField(container, fieldName);
    });
});
