/**
 * Sistema de selectores dinámicos con búsqueda
 * Uso: new DynamicSelect(containerId, apiUrl, onSelect)
 */

class DynamicSelect {
    constructor(containerId, apiUrl, onSelect = null) {
        this.container = document.getElementById(containerId);
        this.apiUrl = apiUrl;
        this.onSelect = onSelect;
        this.selectedItem = null;
        this.options = [];
        this.filteredOptions = [];
        
        this.init();
    }

    async init() {
        // Crear estructura HTML
        this.createHTML();
        
        // Cargar opciones desde API
        await this.loadOptions();
        
        // Agregar event listeners
        this.attachEventListeners();
    }

    createHTML() {
        this.container.innerHTML = `
            <div class="search-container">
                <label>${this.container.dataset.label || 'Selecciona una opción'}</label>
                <div class="search-wrapper">
                    <input
                        type="text"
                        class="search-input"
                        placeholder="Escribe para buscar..."
                        autocomplete="off"
                    >
                    <div class="options-list"></div>
                </div>
                <div class="selected-display"></div>
                <input type="hidden" class="selected-id-input" value="">
            </div>
        `;
    }

    _hiddenInput() {
        return this.container.querySelector('.selected-id-input');
    }

    async loadOptions() {
        try {
            const response = await fetch(this.apiUrl);
            if (!response.ok) throw new Error('Error al cargar opciones');
            
            this.options = await response.json();
            this.filteredOptions = [...this.options];
        } catch (error) {
            console.error('Error cargando opciones:', error);
            this.showMessage('Error al cargar opciones');
        }
    }

    attachEventListeners() {
        const input = this.container.querySelector('.search-input');
        const optionsList = this.container.querySelector('.options-list');

        // Mostrar/ocultar lista y filtrar
        input.addEventListener('input', (e) => {
            this.filterOptions(e.target.value);
            this.renderOptions();
            optionsList.classList.add('visible');
        });

        // Enfocar: mostrar todas las opciones
        input.addEventListener('focus', () => {
            this.filteredOptions = [...this.options];
            this.renderOptions();
            optionsList.classList.add('visible');
        });

        // Ocultar al perder foco (con delay para permitir clic)
        input.addEventListener('blur', () => {
            setTimeout(() => {
                optionsList.classList.remove('visible');
            }, 200);
        });

        // Cerrar al hacer ESC
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                optionsList.classList.remove('visible');
            }
        });
    }

    filterOptions(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        
        if (!term) {
            this.filteredOptions = [...this.options];
        } else {
            this.filteredOptions = this.options.filter(opt => 
                opt.id.toLowerCase().includes(term) || 
                opt.label.toLowerCase().includes(term)
            );
        }
    }

    renderOptions() {
        const optionsList = this.container.querySelector('.options-list');
        
        if (this.filteredOptions.length === 0) {
            optionsList.innerHTML = '<div class="no-results">No hay resultados</div>';
            return;
        }

        optionsList.innerHTML = this.filteredOptions
            .map(opt => `
                <div class="option-item" data-id="${opt.id}">
                    <span class="option-label">${opt.label}</span>
                    <span class="option-id">(${opt.id})</span>
                </div>
            `)
            .join('');

        // Agregar event listeners a opciones
        optionsList.querySelectorAll('.option-item').forEach(item => {
            item.addEventListener('click', () => this.selectOption(item));
        });
    }

    selectOption(item) {
        const id = item.dataset.id;
        const label = item.querySelector('.option-label').textContent;
        
        this.selectedItem = { id, label };

        // Guardar ID en input hidden (scoped al contenedor)
        this._hiddenInput().value = id;
        
        // Actualizar display
        this.updateDisplay();
        
        // Limpiar input y cerrar lista
        const input = this.container.querySelector('.search-input');
        input.value = '';
        this.container.querySelector('.options-list').classList.remove('visible');

        // Callback
        if (this.onSelect) {
            this.onSelect(this.selectedItem);
        }
    }

    updateDisplay() {
        const display = this.container.querySelector('.selected-display');
        
        if (this.selectedItem) {
            display.innerHTML = `
                <div class="selected-value active">
                    <strong>${this.selectedItem.label}</strong><br>
                    <small>ID: ${this.selectedItem.id}</small>
                </div>
            `;
        } else {
            display.innerHTML = '';
        }
    }

    showMessage(msg) {
        const optionsList = this.container.querySelector('.options-list');
        optionsList.innerHTML = `<div class="no-results">${msg}</div>`;
        optionsList.classList.add('visible');
    }

    getValue() {
        return this._hiddenInput().value;
    }

    clear() {
        this.selectedItem = null;
        this._hiddenInput().value = '';
        this.container.querySelector('.search-input').value = '';
        this.container.querySelector('.selected-display').innerHTML = '';
    }
}
