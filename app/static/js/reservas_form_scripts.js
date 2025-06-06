        // Constantes e Variáveis Globais
        const API_BASE_URL_BACKEND = ''; 
        const ORS_API_KEY = '5b3ce3597851110001cf6248850b8ffce4374751a5d867566f4b3269'; 

        // Card 1: Orçamento (Flip Card)
        const budgetFlipCard = document.getElementById('budgetFlipCard'); 
        const budgetFlipCardInner = document.getElementById('budgetFlipCardInner'); 
        const flipBackButton = document.getElementById('flipBackButton'); 

        // Frente do Card 1
        const pickupInput = document.getElementById('pickupLocationBudget');
        const pickupSuggestionsContainer = document.getElementById('pickupSuggestions');
        const dropoffInput = document.getElementById('dropoffLocationBudget');
        const dropoffSuggestionsContainer = document.getElementById('dropoffSuggestions');
        const budgetForm = document.getElementById('budgetForm');
        const calculateBudgetBtn = document.getElementById('calculateBudgetBtn');

        // Verso do Card 1 (apenas resultado e mensagem do orçamento)
        const budgetResult = document.getElementById('budgetResult'); 
        const budgetMessage = document.getElementById('budgetMessage');

        // Card 3: Voucher (Standalone, aparece abaixo do Card 1)
        const voucherCardStandalone = document.getElementById('voucherCardStandalone');
        const voucherSection = document.getElementById('voucherSection');
        const voucherCodeInput = document.getElementById('voucherCodeInput');
        const applyVoucherBtn = document.getElementById('applyVoucherBtn');
        const voucherMessage = document.getElementById('voucherMessage');

        // Card 2: Reserva
        const bookingSectionContainer = document.getElementById('bookingSectionContainer');
        const bookingForm = document.getElementById('bookingForm');
        const bookingMessage = document.getElementById('bookingMessage');
        const submitBookingBtn = document.getElementById('submitBookingBtn');
        
        const countryCodeSelect = document.getElementById('countryCodeSelect');
        const passengerPhoneInput = document.getElementById('passengerPhone');

        // Inputs escondidos para booking
        const pickupLocationBookingInput = document.getElementById('pickupLocationBooking');
        const dropoffLocationBookingInput = document.getElementById('dropoffLocationBooking');
        const passengersBookingInput = document.getElementById('passengersBooking');
        const bagsBookingInput = document.getElementById('bagsBooking');
        const durationMinutesBookingInput = document.getElementById('durationMinutesBooking');
        const appliedVoucherCodeBookingInput = document.getElementById('appliedVoucherCodeBooking');

        // Estado do orçamento
        let currentBudgetData = {
            originalBudgetPreVat: null, finalBudgetPreVat: null, vatPercentage: null,
            vatAmount: null, totalWithVat: null, duration: null, pickup: null,
            dropoff: null, passengers: null, bags: null, appliedVoucherCode: null, discountAmount: 0.0
        };

        const countries = [
            { name: "Portugal", code: "+351", flag: "🇵🇹" }, { name: "Espanha", code: "+34", flag: "🇪🇸" },
            { name: "França", code: "+33", flag: "🇫🇷" }, { name: "Reino Unido", code: "+44", flag: "🇬🇧" },
            { name: "Alemanha", code: "+49", flag: "🇩🇪" }, { name: "Itália", code: "+39", flag: "🇮🇹" },
            { name: "Suíça", code: "+41", flag: "🇨🇭" }, { name: "Bélgica", code: "+32", flag: "🇧🇪" },
            { name: "Países Baixos", code: "+31", flag: "🇳🇱" }, { name: "Brasil", code: "+55", flag: "🇧🇷" },
            { name: "EUA", code: "+1", flag: "🇺🇸" }, { name: "Angola", code: "+244", flag: "🇦🇴" },
            { name: "Moçambique", code: "+258", flag: "🇲🇿" },
        ];

        function populateCountryCodes() {
            if (!countryCodeSelect) return;
            countries.forEach(country => {
                const option = document.createElement('option');
                option.value = country.code;
                option.textContent = `${country.flag} ${country.code} (${country.name})`;
                if (country.code === "+351") option.selected = true;
                countryCodeSelect.appendChild(option);
            });
        }

        function debounce(func, delay) { let timeout; return function(...args) { clearTimeout(timeout); timeout = setTimeout(() => func.apply(this, args), delay); }; }
        
        /**
         * @param {HTMLElement} element
         * @param {boolean} show
         */
        function showHideElement(element, show = true) {
            if (!element) { console.warn("showHideElement: Elemento não encontrado."); return; }
            element.offsetHeight; 
            if (show) {
                element.classList.add('visible');
            } else {
                element.classList.remove('visible');
            }
        }


        function showMessage(element, message, type = 'success') { 
            if (!element) { console.error("showMessage: Elemento de mensagem não encontrado."); return; } 
            element.innerHTML = message; 
            element.className = `message-box message-${type} transitionable-element`; 
            
            element.offsetHeight;
            requestAnimationFrame(() => {
                 element.classList.add('visible');
            });

            const timeoutDuration = (type === 'error' || type === 'info') ? 7000 : 5000;
            setTimeout(() => { 
                if (element) showHideElement(element, false); 
            }, timeoutDuration); 
        }
        
        function formatCurrency(value) { if (value === null || value === undefined || isNaN(parseFloat(value))) return 'N/A'; try { return parseFloat(value).toFixed(2); } catch(e) { console.error("Erro ao formatar moeda:", value, e); return 'Inv.'; } }

        async function fetchAutocompleteSuggestions(query, suggestionsContainer) {
            if (query.length < 3) { suggestionsContainer.innerHTML = ''; suggestionsContainer.style.display = 'none'; return; }
            const url = `https://api.openrouteservice.org/geocode/autocomplete?api_key=${ORS_API_KEY}&text=${encodeURIComponent(query)}&boundary.country=PRT&lang=pt&layers=address,street,venue,locality,county,region`;
            try {
                const response = await fetch(url);
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ message: `Erro HTTP: ${response.statusText}` }));
                    throw new Error(errorData.message || `Erro na API de geocodificação: ${response.statusText}`);
                }
                const data = await response.json();
                displaySuggestions(data.features, suggestionsContainer, query === pickupInput.value ? pickupInput : dropoffInput);
            } catch (error) {
                console.error('Erro no autocomplete:', error);
                suggestionsContainer.innerHTML = `<div class="p-2 text-xs text-red-600">Erro: ${error.message}. Tente novamente.</div>`;
                suggestionsContainer.style.display = 'block'; 
            }
        }

        function displaySuggestions(features, suggestionsContainer, inputElement) {
            suggestionsContainer.innerHTML = '';
            if (features && features.length > 0) {
                features.forEach(feature => {
                    const props = feature.properties;
                    const item = document.createElement('div');
                    item.classList.add('autocomplete-suggestion-item');
                    let mainLabel = props.name || props.label || "Localização desconhecida";
                    let contextParts = [props.street, props.locality, props.county, props.region].filter(Boolean); 
                    if (props.housenumber && props.street && mainLabel.toLowerCase().includes(props.street.toLowerCase())) {
                        contextParts = [props.locality, props.county, props.region].filter(Boolean);
                    } else if (props.street) {
                        if (props.housenumber) mainLabel = `${props.street} ${props.housenumber}`;
                        else mainLabel = props.street;
                        contextParts = [props.locality, props.county, props.region].filter(Boolean);
                    }
                    let displayText = `<span class="suggestion-label">${mainLabel}</span>`;
                    const uniqueContextParts = [...new Set(contextParts.map(p => p.trim()))]; 
                    let displayContext = uniqueContextParts.filter(p => p && mainLabel.toLowerCase() !== p.toLowerCase()).join(', ');
                    if (displayContext) displayText += `<span class="suggestion-context">${displayContext}</span>`;
                    item.innerHTML = displayText;
                    item.onclick = () => {
                        inputElement.value = props.label || mainLabel; 
                        suggestionsContainer.innerHTML = '';
                        suggestionsContainer.style.display = 'none';
                    };
                    suggestionsContainer.appendChild(item);
                });
                suggestionsContainer.style.display = 'block';
            } else {
                suggestionsContainer.innerHTML = `<div class="p-2 text-xs text-gray-500">Nenhuma sugestão.</div>`;
                suggestionsContainer.style.display = 'block';
            }
        }

        pickupInput.addEventListener('input', debounce(() => fetchAutocompleteSuggestions(pickupInput.value, pickupSuggestionsContainer), 350));
        dropoffInput.addEventListener('input', debounce(() => fetchAutocompleteSuggestions(dropoffInput.value, dropoffSuggestionsContainer), 350));

        document.addEventListener('click', function(event) {
            if (pickupSuggestionsContainer && !pickupInput.contains(event.target) && !pickupSuggestionsContainer.contains(event.target)) {
                pickupSuggestionsContainer.style.display = 'none';
            }
            if (dropoffSuggestionsContainer && !dropoffInput.contains(event.target) && !dropoffSuggestionsContainer.contains(event.target)) {
                dropoffSuggestionsContainer.style.display = 'none';
            }
        });

        function updateBudgetDisplay() {
            if (!budgetResult) return;
            if (currentBudgetData.finalBudgetPreVat === null) { 
                showHideElement(budgetResult, false);
                return;
            }
            let html = '';
            if (currentBudgetData.discountAmount > 0 && currentBudgetData.originalBudgetPreVat !== null) {
                html += `<div class="budget-line"><span>Preço Base (s/IVA):</span> <span class="budget-original-price">${formatCurrency(currentBudgetData.originalBudgetPreVat)} €</span></div>`;
                html += `<div class="budget-line"><span>Desconto (${currentBudgetData.appliedVoucherCode || 'Promoção'}):</span> <strong>-${formatCurrency(currentBudgetData.discountAmount)} €</strong></div>`;
            }
            html += `<div class="budget-line"><span>Subtotal (s/IVA):</span> <strong>${formatCurrency(currentBudgetData.finalBudgetPreVat)} €</strong></div>`;
            
            if (typeof currentBudgetData.vatPercentage === 'number' && typeof currentBudgetData.vatAmount === 'number') {
                html += `<div class="budget-line"><span>IVA (${currentBudgetData.vatPercentage.toFixed(1)}%):</span> <span>+ ${formatCurrency(currentBudgetData.vatAmount)} €</span></div>`;
            } else {
                html += `<div class="budget-line"><span>IVA:</span> <span>N/A</span></div>`;
            }
            if (typeof currentBudgetData.totalWithVat === 'number') {
                html += `<div class="budget-total"><strong>Total a Pagar: ${formatCurrency(currentBudgetData.totalWithVat)} €</strong></div>`;
            } else {
                 html += `<div class="budget-total"><strong>Total a Pagar: N/A</strong></div>`;
            }

            if (currentBudgetData.duration !== null && typeof currentBudgetData.duration === 'number') {
                html += `<div class="mt-2 text-sm">Duração Estimada: ${currentBudgetData.duration} minutos</div>`;
            } else {
                 html += `<div class="mt-2 text-sm">Duração Estimada: N/A</div>`;
            }
            budgetResult.innerHTML = html;
            showHideElement(budgetResult, true);
        }
        
        function setBookingSectionActive(isActive) {
            if (!bookingSectionContainer || !bookingForm || !submitBookingBtn) return;
            if (isActive) {
                bookingSectionContainer.classList.remove('section-disabled');
                Array.from(bookingForm.elements).forEach(el => el.disabled = false);
                if(currentBudgetData.finalBudgetPreVat !== null) {
                     submitBookingBtn.disabled = false;
                     submitBookingBtn.classList.remove('btn-disabled');
                } else {
                     submitBookingBtn.disabled = true;
                     submitBookingBtn.classList.add('btn-disabled');
                }
            } else {
                bookingSectionContainer.classList.add('section-disabled');
                Array.from(bookingForm.elements).forEach(el => el.disabled = true);
                submitBookingBtn.disabled = true; 
                submitBookingBtn.classList.add('btn-disabled');
            }
        }

        budgetForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            showHideElement(budgetResult, false); 
            showHideElement(budgetMessage, false);
            showHideElement(voucherCardStandalone, false);
            showHideElement(voucherMessage, false); 
            if(voucherCodeInput) voucherCodeInput.value = '';
            
            setBookingSectionActive(false); 

            if(calculateBudgetBtn) {
                calculateBudgetBtn.disabled = true; 
                calculateBudgetBtn.classList.add('btn-disabled'); 
                calculateBudgetBtn.textContent = 'Calculando...';
            }
            
            currentBudgetData = {
                originalBudgetPreVat: null, finalBudgetPreVat: null, vatPercentage: null, vatAmount: null, totalWithVat: null,
                duration: null, pickup: null, dropoff: null, passengers: null, bags: null, appliedVoucherCode: null, discountAmount: 0.0
            };

            const formData = new FormData(budgetForm);
            const data = {
                pickupLocation: formData.get('pickupLocation'), dropoffLocation: formData.get('dropoffLocation'),
                passengers: parseInt(formData.get('passengers')), bags: parseInt(formData.get('bags'))
            };

            if (!data.pickupLocation || !data.dropoffLocation) {
                 showMessage(budgetMessage, 'Preencha partida e destino.', 'error');
                 updateBudgetDisplay(); 
                 if (budgetFlipCard) budgetFlipCard.classList.add('is-flipped');
                 if(calculateBudgetBtn) {
                    calculateBudgetBtn.disabled = false; 
                    calculateBudgetBtn.classList.remove('btn-disabled'); 
                    calculateBudgetBtn.textContent = 'Calcular Orçamento';
                 }
                 return;
            }
            try {
                const response = await fetch(`${API_BASE_URL_BACKEND}/calculate-budget`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
                });
                const result = await response.json();
                
                if (response.ok) {
                    currentBudgetData.pickup = data.pickupLocation;
                    currentBudgetData.dropoff = data.dropoffLocation;
                    currentBudgetData.passengers = data.passengers;
                    currentBudgetData.bags = data.bags;
                    
                    currentBudgetData.originalBudgetPreVat = result.original_budget_pre_vat;
                    currentBudgetData.finalBudgetPreVat = result.original_budget_pre_vat;
                    currentBudgetData.vatPercentage = result.vat_percentage;
                    currentBudgetData.vatAmount = result.vat_amount;
                    currentBudgetData.totalWithVat = result.total_with_vat;
                    currentBudgetData.duration = result.duration_minutes;
                    
                    currentBudgetData.appliedVoucherCode = null; 
                    currentBudgetData.discountAmount = 0.0;     

                    updateBudgetDisplay();
                    showMessage(budgetMessage, `Orçamento calculado.`, 'success');
                    showHideElement(voucherCardStandalone, true);
                    setBookingSectionActive(true);
                } else {
                    showMessage(budgetMessage, `Erro: ${result.error || 'Serviço indisponível.'}`, 'error');
                    updateBudgetDisplay(); 
                    setBookingSectionActive(false);
                }
            } catch (error) {
                console.error("Erro no cálculo do orçamento:", error);
                showMessage(budgetMessage, `Erro de comunicação. Verifique a consola.`, 'error');
                updateBudgetDisplay(); 
                setBookingSectionActive(false);
            } finally {
                if(calculateBudgetBtn) {
                    calculateBudgetBtn.disabled = false; 
                    calculateBudgetBtn.classList.remove('btn-disabled'); 
                    calculateBudgetBtn.textContent = 'Calcular Orçamento';
                }
                if (budgetFlipCard) budgetFlipCard.classList.add('is-flipped'); 
            }
        });

        if (flipBackButton) {
            flipBackButton.addEventListener('click', () => {
                if (budgetFlipCard) budgetFlipCard.classList.remove('is-flipped');
                
                showHideElement(budgetResult, false);
                showHideElement(budgetMessage, false);
                showHideElement(voucherCardStandalone, false);
                showHideElement(voucherMessage, false);
                if(voucherCodeInput) voucherCodeInput.value = '';
                
                setBookingSectionActive(false); 
                currentBudgetData = { 
                    originalBudgetPreVat: null, finalBudgetPreVat: null, vatPercentage: null, vatAmount: null, totalWithVat: null,
                    duration: null, pickup: null, dropoff: null, passengers: null, bags: null, appliedVoucherCode: null, discountAmount: 0.0
                };
            });
        }

        function round(value, decimals) { 
            if (typeof value !== 'number' || typeof decimals !== 'number') return NaN;
            return Number(Math.round(value + 'e' + decimals) + 'e-' + decimals);
        }

        if(applyVoucherBtn) {
            applyVoucherBtn.addEventListener('click', async () => {
                const code = voucherCodeInput.value.trim().toUpperCase();
                showHideElement(voucherMessage, false);
                if (!code) { showMessage(voucherMessage, 'Insira um código.', 'error'); return; }
                if (currentBudgetData.originalBudgetPreVat === null) { showMessage(voucherMessage, 'Calcule o orçamento base primeiro.', 'error'); return; }
                
                applyVoucherBtn.disabled = true; applyVoucherBtn.classList.add('btn-disabled'); applyVoucherBtn.textContent = 'A validar...';
                try {
                    const response = await fetch(`${API_BASE_URL_BACKEND}/validate-voucher`, {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ voucher_code: code, original_budget_pre_vat: currentBudgetData.originalBudgetPreVat })
                    });
                    const result = await response.json();
                    
                    if (response.ok && result.valid) {
                        currentBudgetData.appliedVoucherCode = result.voucher_code;
                        currentBudgetData.discountAmount = result.discount_amount;
                        currentBudgetData.finalBudgetPreVat = result.final_budget_pre_vat;
                        currentBudgetData.vatPercentage = result.vat_percentage; 
                        currentBudgetData.vatAmount = result.vat_amount;         
                        currentBudgetData.totalWithVat = result.total_with_vat;   
                        showMessage(voucherMessage, `Voucher "${result.voucher_code}" aplicado!`, 'success');
                    } else {
                        showMessage(voucherMessage, `Erro: ${result.error || 'Não foi possível aplicar.'}`, 'error');
                        currentBudgetData.appliedVoucherCode = null;
                        currentBudgetData.discountAmount = 0.0;
                        currentBudgetData.finalBudgetPreVat = currentBudgetData.originalBudgetPreVat;
                        if (currentBudgetData.originalBudgetPreVat !== null && typeof currentBudgetData.originalBudgetPreVat === 'number') {
                            const opv = currentBudgetData.originalBudgetPreVat;
                            const vp = currentBudgetData.vatPercentage; 
                            if (vp !== null && typeof vp === 'number') {
                                currentBudgetData.vatAmount = round(opv * (vp / 100.0), 2);
                                currentBudgetData.totalWithVat = round(opv + currentBudgetData.vatAmount, 2);
                            } else { 
                                currentBudgetData.vatAmount = null;
                                currentBudgetData.totalWithVat = null;
                            }
                        } else { 
                            currentBudgetData.vatAmount = null;
                            currentBudgetData.totalWithVat = null;
                        }
                    }
                    updateBudgetDisplay(); 
                } catch (error) {
                    console.error("Erro na validação do voucher:", error);
                    showMessage(voucherMessage, `Erro de comunicação. Tente novamente.`, 'error');
                    currentBudgetData.appliedVoucherCode = null; currentBudgetData.discountAmount = 0.0;
                    currentBudgetData.finalBudgetPreVat = currentBudgetData.originalBudgetPreVat;
                    if (currentBudgetData.originalBudgetPreVat !== null && typeof currentBudgetData.originalBudgetPreVat === 'number') {
                        const opv = currentBudgetData.originalBudgetPreVat;
                        const vp = currentBudgetData.vatPercentage;
                        if (vp !== null && typeof vp === 'number') {
                            currentBudgetData.vatAmount = round(opv * (vp / 100.0), 2);
                            currentBudgetData.totalWithVat = round(opv + currentBudgetData.vatAmount, 2);
                        } else {
                            currentBudgetData.vatAmount = null;
                            currentBudgetData.totalWithVat = null;
                        }
                    } else {
                        currentBudgetData.vatAmount = null;
                        currentBudgetData.totalWithVat = null;
                    }
                    updateBudgetDisplay();
                } finally {
                    applyVoucherBtn.disabled = false; applyVoucherBtn.classList.remove('btn-disabled'); applyVoucherBtn.textContent = 'Aplicar';
                }
            });
        }

        if(bookingForm) {
            bookingForm.addEventListener('submit', async (event) => {
                event.preventDefault();
                showHideElement(bookingMessage, false);
                if (currentBudgetData.finalBudgetPreVat === null) { 
                     showMessage(bookingMessage, 'Calcule o orçamento antes de submeter.', 'error'); return;
                }
                const phoneValue = passengerPhoneInput.value.trim();
                if (!document.getElementById('passengerName').value.trim()) { showMessage(bookingMessage, 'Nome é obrigatório.', 'error'); document.getElementById('passengerName').focus(); return; }
                if (!phoneValue) { showMessage(bookingMessage, 'Telefone é obrigatório.', 'error'); passengerPhoneInput.focus(); return; }
                if (!document.getElementById('date').value || !document.getElementById('time').value) { showMessage(bookingMessage, 'Data e Hora são obrigatórias.', 'error'); return; }
                
                submitBookingBtn.disabled = true; submitBookingBtn.classList.add('btn-disabled'); submitBookingBtn.textContent = 'A submeter...';
                
                const selectedCountryCode = countryCodeSelect.value;
                pickupLocationBookingInput.value = currentBudgetData.pickup;
                dropoffLocationBookingInput.value = currentBudgetData.dropoff;
                passengersBookingInput.value = currentBudgetData.passengers;
                bagsBookingInput.value = currentBudgetData.bags;
                durationMinutesBookingInput.value = currentBudgetData.duration;
                appliedVoucherCodeBookingInput.value = currentBudgetData.appliedVoucherCode || '';
                
                const formData = new FormData(bookingForm);
                const data = {
                    passengerName: formData.get('passengerName'),
                    passengerPhone: selectedCountryCode + formData.get('passengerPhone').replace(/\s+/g, ''),
                    date: formData.get('date'), time: formData.get('time'),
                    instructions: formData.get('instructions'),
                    pickupLocation: formData.get('pickupLocation'), 
                    dropoffLocation: formData.get('dropoffLocation'), 
                    passengers: parseInt(formData.get('passengers')), 
                    bags: parseInt(formData.get('bags')),             
                    duration_minutes: parseInt(formData.get('duration_minutes')), 
                    voucher_code: formData.get('voucher_code') || null 
                };

                try {
                    const response = await fetch(`${API_BASE_URL_BACKEND}/submit-booking`, {
                        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data),
                    });
                    const result = await response.json();
                    if (response.status === 201 || response.ok) { 
                        showMessage(bookingMessage, `Pedido submetido! ID: ${result.bookingId}. Total: ${formatCurrency(result.total_with_vat)} €. ${result.message || ''}`, 'success');
                        budgetForm.reset(); bookingForm.reset();
                        if(countryCodeSelect) countryCodeSelect.value = "+351"; 
                        
                        if (budgetFlipCard) budgetFlipCard.classList.remove('is-flipped');
                        showHideElement(budgetResult, false); showHideElement(budgetMessage, false);
                        showHideElement(voucherCardStandalone, false);
                        showHideElement(voucherMessage, false);
                        if(voucherCodeInput) voucherCodeInput.value = '';

                        setBookingSectionActive(false); 
                        currentBudgetData = { 
                            originalBudgetPreVat: null, finalBudgetPreVat: null, vatPercentage: null, vatAmount: null, totalWithVat: null,
                            duration: null, pickup: null, dropoff: null, passengers: null, bags: null, appliedVoucherCode: null, discountAmount: 0.0
                        };
                        initializeDateTime(); 
                    } else {
                        showMessage(bookingMessage, `Erro: ${result.error || 'Tente novamente.'}`, 'error');
                    }
                } catch (error) {
                    console.error("Erro na submissão da reserva:", error);
                    showMessage(bookingMessage, `Erro de comunicação. Verifique a consola.`, 'error');
                } finally {
                    if (bookingSectionContainer && bookingSectionContainer.classList.contains('section-disabled')) {
                        submitBookingBtn.disabled = true;
                        submitBookingBtn.classList.add('btn-disabled');
                    } else if (submitBookingBtn) {
                        submitBookingBtn.disabled = false;
                        submitBookingBtn.classList.remove('btn-disabled');
                    }
                    if(submitBookingBtn) submitBookingBtn.textContent = 'Submeter Pedido';
                }
            });
        }

        function initializeDateTime() {
            const dateInput = document.getElementById('date');
            const timeInput = document.getElementById('time');
            if (!dateInput || !timeInput) return;

            const now = new Date();
            const today = now.toISOString().split('T')[0];
            dateInput.value = today; dateInput.min = today;
            now.setHours(now.getHours() + 1);
            const minutes = now.getMinutes();
            const roundedMinutes = Math.ceil(minutes / 15) * 15;
            if (roundedMinutes >= 60) { now.setHours(now.getHours() + 1); now.setMinutes(0); }
            else { now.setMinutes(roundedMinutes); }
            timeInput.value = now.toTimeString().slice(0,5);
        }

        document.addEventListener('DOMContentLoaded', () => {
            initializeDateTime();
            populateCountryCodes();
            [budgetResult, budgetMessage, voucherMessage, bookingMessage].forEach(el => {
                if(el) el.classList.add('transitionable-element'); 
            });
            setBookingSectionActive(false); 
        });
