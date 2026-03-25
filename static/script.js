const API_BASE = '';

let token = localStorage.getItem('token');
let currentUser = null;
let categories = [];
let userSettings = {
    notification_enabled: true,
    five_minute_notifications: true
};

// Элементы DOM
const authSection = document.getElementById('auth-section');
const loginForm = document.getElementById('login-form');
const userInfo = document.getElementById('user-info');
const userEmailSpan = document.getElementById('user-email');
const logoutBtn = document.getElementById('logout-btn');
const appMain = document.getElementById('app');

// Вкладки
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

// Подписки
const subsListDiv = document.getElementById('subs-list');
const addSubBtn = document.getElementById('add-sub-btn');
const importEmailBtn = document.getElementById('import-email-btn');

// Категории
const categoriesListDiv = document.getElementById('categories-list');
const addCategoryBtn = document.getElementById('add-category-btn');

// Уведомления
const notificationsBtn = document.getElementById('notifications-btn');
const notificationsPanel = document.getElementById('notifications-panel');
const notificationsList = document.getElementById('notifications-list');
const notificationToggle = document.getElementById('notification-toggle');
const fiveMinuteToggle = document.getElementById('five-minute-toggle');

// Аналитика
const totalMonthlySpan = document.getElementById('total-monthly');
const upcomingList = document.getElementById('upcoming-list');
const urgentList = document.getElementById('urgent-list');
const adviceListDiv = document.getElementById('advice-list');

// Импорт
const importStatus = document.getElementById('import-status');
const importProgress = document.getElementById('import-progress-container');
const importProgressBar = document.getElementById('import-progress-bar');
const importProgressText = document.getElementById('import-progress-text');
const statProcessed = document.getElementById('stat-processed');
const statFound = document.getElementById('stat-found');
const statTime = document.getElementById('stat-time');
const importResults = document.getElementById('import-results');
const importResultsContent = document.getElementById('import-results-content');

// Модалка подписки
const subModal = document.getElementById('sub-modal');
const subModalTitle = document.getElementById('modal-title');
const subForm = document.getElementById('sub-form');
const subClose = document.querySelector('#sub-modal .close');
const subIdInput = document.getElementById('sub-id');
const subName = document.getElementById('sub-name');
const subCategory = document.getElementById('sub-category');
const subPrice = document.getElementById('sub-price');
const subCurrency = document.getElementById('sub-currency');
const subPeriod = document.getElementById('sub-period');
const subNextPayment = document.getElementById('sub-next-payment');
const subNextTime = document.getElementById('sub-next-time');
const subAutoRenewal = document.getElementById('sub-auto-renewal');

// Модалка категории
const categoryModal = document.getElementById('category-modal');
const categoryModalTitle = document.getElementById('category-modal-title');
const categoryForm = document.getElementById('category-form');
const categoryClose = document.querySelector('#category-modal .close');
const categoryIdInput = document.getElementById('category-id');
const categoryName = document.getElementById('category-name');
const categoryColor = document.getElementById('category-color');
const categoryIsTest = document.getElementById('category-is-test');

let categoryChart = null;
let importStartTime = null;

// --- Утилиты ---
async function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const options = {
        method,
        headers,
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    try {
        const response = await fetch(API_BASE + endpoint, options);

        // Проверяем статус 401
        if (response.status === 401) {
            console.log('Unauthorized, clearing token');
            localStorage.removeItem('token');
            token = null;
            currentUser = null;
            updateUIForAuth();

            // Показываем сообщение пользователю
            alert('Сессия истекла. Пожалуйста, войдите снова.');

            throw new Error('Сессия истекла. Пожалуйста, войдите снова.');
        }

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Ошибка ${response.status}`);
        }

        // Для пустых ответов возвращаем null
        const text = await response.text();
        return text ? JSON.parse(text) : null;

    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

// --- Переключение вкладок ---
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;

        tabBtns.forEach(b => b.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(tab).classList.add('active');
    });
});

// --- Загрузка настроек пользователя ---
async function loadUserSettings() {
    if (!token) return;
    try {
        const settings = await apiRequest('/user/settings');
        userSettings = settings;

        if (notificationToggle) {
            notificationToggle.checked = settings.notification_enabled;
        }
        if (fiveMinuteToggle) {
            fiveMinuteToggle.checked = settings.five_minute_notifications;
        }
    } catch (error) {
        console.error('Ошибка загрузки настроек:', error);
    }
}

async function saveUserSettings() {
    if (!token) return;
    try {
        const settings = await apiRequest('/user/settings', 'POST', userSettings);
        userSettings = settings;
        showNotification('Настройки сохранены', 'success');
    } catch (error) {
        console.error('Ошибка сохранения настроек:', error);
        showNotification('Ошибка сохранения настроек', 'error');
    }
}

// --- Уведомления ---
async function loadNotifications() {
    if (!token) return;
    try {
        const notifications = await apiRequest('/notifications');
        renderNotifications(notifications);
    } catch (error) {
        console.error('Ошибка загрузки уведомлений:', error);
    }
}

function renderNotifications(notifications) {
    if (!notifications || !notifications.length) {
        notificationsList.innerHTML = '<li class="notification-item">Нет уведомлений</li>';
        return;
    }

    notificationsList.innerHTML = notifications.map(n => {
        let icon = '🔔';
        let typeClass = '';

        if (n.type === 'test') {
            icon = '🧪';
            typeClass = 'test';
        } else if (n.type === 'five_minute') {
            icon = '🚨';
            typeClass = 'urgent';
        } else if (n.type === 'upcoming') {
            icon = '⚠️';
            typeClass = 'upcoming';
        }

        const date = new Date(n.sent_at);
        const formattedDate = date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

        return `
            <li class="notification-item ${typeClass}">
                <div class="notification-icon">${icon}</div>
                <div class="notification-content">
                    <div class="notification-title">${n.subscription_name}</div>
                    <div class="notification-message">${n.message}</div>
                    <div class="notification-time">${formattedDate}</div>
                </div>
            </li>
        `;
    }).join('');
}

if (notificationsBtn) {
    notificationsBtn.addEventListener('click', () => {
        notificationsPanel.classList.toggle('active');
        if (notificationsPanel.classList.contains('active')) {
            loadNotifications();
        }
    });
}

document.addEventListener('click', (e) => {
    if (notificationsPanel && !notificationsPanel.contains(e.target) && !notificationsBtn.contains(e.target)) {
        notificationsPanel.classList.remove('active');
    }
});

if (notificationToggle) {
    notificationToggle.addEventListener('change', async (e) => {
        if (!token) return;
        userSettings.notification_enabled = e.target.checked;
        await saveUserSettings();
    });
}

if (fiveMinuteToggle) {
    fiveMinuteToggle.addEventListener('change', async (e) => {
        if (!token) return;
        userSettings.five_minute_notifications = e.target.checked;
        await saveUserSettings();
    });
}

// --- Загрузка категорий ---
async function loadCategories() {
    if (!token) return [];
    try {
        categories = await apiRequest('/categories');
        updateCategorySelect();
        renderCategories();
        return categories;
    } catch (error) {
        console.error('Ошибка загрузки категорий:', error);
        return [];
    }
}

function updateCategorySelect() {
    subCategory.innerHTML = '<option value="">Выберите категорию</option>';
    categories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat.id;
        option.textContent = cat.name + (cat.is_test ? ' 🧪' : '');
        option.style.color = cat.color;
        subCategory.appendChild(option);
    });
}

function renderCategories() {
    if (!categories.length) {
        categoriesListDiv.innerHTML = '<p>У вас пока нет категорий. Создайте первую!</p>';
        return;
    }

    let html = '';
    categories.forEach(cat => {
        html += `
            <div class="category-card" style="border-left-color: ${cat.color}">
                <div class="category-info">
                    <h3>${cat.name} ${cat.is_test ? '🧪' : ''}</h3>
                    <div class="category-count">${cat.subscription_count} подписок</div>
                </div>
                <div class="category-actions">
                    <button class="category-edit" onclick="editCategory(${cat.id})">✎</button>
                    <button class="category-delete" onclick="deleteCategory(${cat.id})" ${cat.subscription_count > 0 ? 'disabled' : ''}>🗑</button>
                </div>
            </div>
        `;
    });
    categoriesListDiv.innerHTML = html;
}

// --- CRUD категорий ---
window.editCategory = function(id) {
    const category = categories.find(c => c.id === id);
    if (!category) return;

    categoryIdInput.value = category.id;
    categoryName.value = category.name;
    categoryColor.value = category.color;
    categoryIsTest.checked = category.is_test;

    categoryModalTitle.textContent = 'Редактировать категорию';
    categoryModal.style.display = 'flex';
};

window.deleteCategory = async function(id) {
    const category = categories.find(c => c.id === id);
    if (category.subscription_count > 0) {
        alert('Нельзя удалить категорию, в которой есть подписки');
        return;
    }

    if (!confirm('Удалить категорию?')) return;

    try {
        await apiRequest(`/categories/${id}`, 'DELETE');
        await loadCategories();
    } catch (error) {
        alert(error.message);
    }
};

addCategoryBtn.addEventListener('click', () => {
    categoryIdInput.value = '';
    categoryForm.reset();
    categoryColor.value = '#3498db';
    categoryIsTest.checked = false;
    categoryModalTitle.textContent = 'Добавить категорию';
    categoryModal.style.display = 'flex';
});

categoryForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const categoryData = {
        name: categoryName.value,
        color: categoryColor.value,
        is_test: categoryIsTest.checked
    };

    const id = categoryIdInput.value;

    try {
        if (id) {
            await apiRequest(`/categories/${id}`, 'PUT', categoryData);
        } else {
            await apiRequest('/categories', 'POST', categoryData);
        }

        categoryModal.style.display = 'none';
        await loadCategories();
    } catch (error) {
        alert(error.message);
    }
});

// --- Загрузка подписок ---
async function loadSubscriptions() {
    if (!token) return;
    try {
        const subs = await apiRequest('/subscriptions');
        renderSubscriptions(subs);
    } catch (error) {
        console.error('Ошибка загрузки подписок:', error);
    }
}

function renderSubscriptions(subs) {
    if (!subs.length) {
        subsListDiv.innerHTML = '<p>У вас пока нет подписок. Добавьте первую!</p>';
        return;
    }

    let html = '';
    subs.forEach(sub => {
        const nextDate = new Date(sub.next_payment);
        const formattedDate = nextDate.toLocaleDateString('ru-RU') + ' ' +
                             nextDate.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        const isTest = sub.category_is_test ? 'test-sub' : '';
        const importedBadge = sub.imported_from ? '<span class="imported-badge">📥</span>' : '';

        html += `
            <div class="sub-card ${isTest}" data-id="${sub.id}" style="border-left-color: ${sub.category_color}">
                <h3>${sub.name} ${sub.category_is_test ? '🧪' : ''} ${importedBadge}</h3>
                <span class="category-badge" style="background-color: ${sub.category_color}">${sub.category_name}</span>
                <div class="price">${sub.price} ${sub.currency}</div>
                <div class="next-payment">След. платёж: ${formattedDate} (${sub.period})</div>
                <div class="auto-renewal">Автопродление: ${sub.auto_renewal ? '✅' : '❌'}</div>
                <div class="actions">
                    <button class="edit-btn" onclick="editSub(${sub.id})">✎</button>
                    <button class="delete-btn" onclick="deleteSub(${sub.id})">🗑</button>
                    ${sub.category_is_test ? `<button class="test-btn" onclick="sendTestNotification(${sub.id})">📧 Тест</button>` : ''}
                </div>
            </div>
        `;
    });
    subsListDiv.innerHTML = html;
}

// --- CRUD подписок ---
window.editSub = async function(id) {
    if (!token) return;
    try {
        const subs = await apiRequest('/subscriptions');
        const sub = subs.find(s => s.id === id);
        if (!sub) return;

        subIdInput.value = sub.id;
        subName.value = sub.name;
        subCategory.value = sub.category_id;
        subPrice.value = sub.price;
        subCurrency.value = sub.currency;
        subPeriod.value = sub.period;

        const d = new Date(sub.next_payment);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');

        subNextPayment.value = `${year}-${month}-${day}`;
        subNextTime.value = `${hours}:${minutes}`;
        subAutoRenewal.checked = sub.auto_renewal;

        subModalTitle.textContent = 'Редактировать подписку';
        subModal.style.display = 'flex';
    } catch (error) {
        alert(error.message);
    }
};

window.deleteSub = async function(id) {
    if (!token) return;
    if (!confirm('Удалить подписку?')) return;
    try {
        await apiRequest(`/subscriptions/${id}`, 'DELETE');
        await Promise.all([loadSubscriptions(), loadAnalytics(), loadAIAdvice(), loadCategories()]);
    } catch (error) {
        alert(error.message);
    }
};

addSubBtn.addEventListener('click', () => {
    if (!token) {
        alert('Пожалуйста, войдите в систему');
        return;
    }
    if (!categories.length) {
        alert('Сначала создайте хотя бы одну категорию');
        return;
    }

    subIdInput.value = '';
    subForm.reset();
    subAutoRenewal.checked = true;

    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');

    subNextPayment.value = `${year}-${month}-${day}`;
    subNextTime.value = `${hours}:${minutes}`;

    subModalTitle.textContent = 'Добавить подписку';
    subModal.style.display = 'flex';
});

subForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!token) {
        alert('Пожалуйста, войдите в систему');
        return;
    }

    if (!subCategory.value) {
        alert('Выберите категорию');
        return;
    }

    const dateTimeStr = `${subNextPayment.value}T${subNextTime.value}:00`;

    const subData = {
        category_id: parseInt(subCategory.value),
        name: subName.value,
        price: parseFloat(subPrice.value),
        currency: subCurrency.value,
        period: subPeriod.value,
        next_payment: new Date(dateTimeStr).toISOString(),
        auto_renewal: subAutoRenewal.checked
    };

    const id = subIdInput.value;

    try {
        if (id) {
            await apiRequest(`/subscriptions/${id}`, 'PUT', subData);
        } else {
            await apiRequest('/subscriptions', 'POST', subData);
        }

        subModal.style.display = 'none';
        await Promise.all([loadSubscriptions(), loadAnalytics(), loadAIAdvice(), loadCategories()]);
    } catch (error) {
        alert(error.message);
    }
});

// --- Аналитика ---
async function loadAnalytics() {
    if (!token) return;
    try {
        const analytics = await apiRequest('/analytics');
        renderAnalytics(analytics);
    } catch (error) {
        console.error('Ошибка загрузки аналитики:', error);
    }
}

function renderAnalytics(data) {
    totalMonthlySpan.textContent = data.total_monthly;

    // Срочные списания (5 минут)
    if (data.urgent && data.urgent.length) {
        urgentList.innerHTML = data.urgent.map(u =>
            `<li class="urgent-item">
                🚨 ${u.name} (${u.category}) — ${u.amount} ${u.currency}
                <br><small>через ${u.minutes_left} мин.</small>
            </li>`
        ).join('');
    } else {
        urgentList.innerHTML = '<li>Нет срочных списаний</li>';
    }

    // Ближайшие списания (7 дней)
    if (data.upcoming && data.upcoming.length) {
        upcomingList.innerHTML = data.upcoming.map(u =>
            `<li>
                ${u.name} (${u.category}) — ${u.amount} ${u.currency}
                <br><small>через ${u.days_left} дн.</small>
            </li>`
        ).join('');
    } else {
        upcomingList.innerHTML = '<li>Нет ближайших списаний</li>';
    }

    // График по категориям
    const ctx = document.getElementById('categoryChart').getContext('2d');
    if (categoryChart) categoryChart.destroy();

    const labels = Object.keys(data.by_category);
    const values = Object.values(data.by_category);
    const colors = labels.map(label => {
        const cat = categories.find(c => c.name === label);
        return cat ? cat.color : '#8E8E93';
    });

    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 0,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: {
                            family: '-apple-system',
                            size: 12
                        },
                        padding: 20
                    }
                }
            }
        }
    });
}

// --- AI советы ---
async function loadAIAdvice() {
    if (!token) return;
    try {
        const advice = await apiRequest('/ai-analysis');
        renderAdvice(advice);
    } catch (error) {
        console.error('Ошибка загрузки советов AI:', error);
    }
}

function renderAdvice(adviceList) {
    if (!adviceList || !adviceList.length) {
        adviceListDiv.innerHTML = '<div class="advice-item">💡 Загрузка рекомендаций...</div>';
        return;
    }

    let html = '';
    adviceList.forEach(item => {
        html += `<div class="advice-item">${item.advice}</div>`;
    });
    adviceListDiv.innerHTML = html;
}

// --- Тестовое уведомление ---
window.sendTestNotification = async function(subscriptionId) {
    if (!token) {
        alert('Пожалуйста, войдите в систему');
        return;
    }
    try {
        await apiRequest(`/test-notification/${subscriptionId}`, 'POST');
        alert('Тестовое уведомление отправлено! Проверьте почту.');
    } catch (error) {
        alert('Ошибка отправки уведомления: ' + error.message);
    }
};

// --- Функция для показа уведомлений ---
function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `import-toast ${type}`;

    const lines = message.split('\n');
    const formattedMessage = lines.map(line => {
        if (line.includes('✅') || line.includes('🔄')) {
            return `<strong>${line}</strong>`;
        }
        if (line.includes('•')) {
            return `<span style="color: var(--ios-blue);">${line}</span>`;
        }
        return line;
    }).join('<br>');

    toast.innerHTML = `
        <div class="toast-header">
            <span class="toast-icon">${type === 'success' ? '📱' : type === 'error' ? '❌' : 'ℹ️'}</span>
            <span class="toast-title">${type === 'success' ? 'Импорт завершен' : type === 'error' ? 'Ошибка' : 'Информация'}</span>
            <button class="toast-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
        <div class="toast-body">
            ${formattedMessage}
        </div>
    `;

    document.body.appendChild(toast);

    // Автоматически скрываем через 8 секунд
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }
    }, 8000);
}

// --- Импорт с почты ---
window.startEmailImport = async function() {
    const provider = document.getElementById('email-provider').value;
    const email = document.getElementById('import-email').value;
    const password = document.getElementById('import-password').value;

    if (!email || !password) {
        alert('Введите email и пароль приложения');
        return;
    }

    // Показываем прогресс
    importStatus.style.display = 'none';
    importProgress.style.display = 'block';
    importResults.style.display = 'none';

    importStartTime = Date.now();
    let progress = 0;

    // Анимируем прогресс
    const progressInterval = setInterval(() => {
        progress = Math.min(progress + Math.random() * 2, 90);
        importProgressBar.style.width = progress + '%';

        const elapsed = Math.floor((Date.now() - importStartTime) / 1000);
        statTime.textContent = elapsed;
        importProgressText.innerHTML = `🔍 Поиск подписок... ${Math.floor(progress)}%`;
    }, 500);

    try {
        let endpoint = '/import/email';
        if (provider !== 'auto') {
            endpoint = `/import/${provider}`;
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка импорта');
        }

        const result = await response.json();

        // Завершаем прогресс
        clearInterval(progressInterval);
        importProgressBar.style.width = '100%';
        importProgressText.innerHTML = '✅ Импорт запущен!';

        // Показываем результаты
        setTimeout(() => {
            importProgress.style.display = 'none';
            importResults.style.display = 'block';

            // Показываем красивое уведомление
            showNotification(
                `✅ Импорт успешно запущен!\n\n` +
                `📧 Почта: ${email}\n` +
                `📊 Поиск подписок начат\n` +
                `⏱ Результат придет на email`,
                'success'
            );

            importResultsContent.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <div style="font-size: 3rem; margin-bottom: 16px;">📱</div>
                    <h3 style="color: var(--ios-blue); margin-bottom: 12px;">Импорт запущен!</h3>
                    <p style="color: var(--ios-gray);">Результат придет на <strong>${email}</strong></p>
                    <p style="color: var(--ios-gray); font-size: 0.9rem; margin-top: 16px;">⏱ Это может занять несколько минут</p>
                </div>
            `;
        }, 1000);

    } catch (error) {
        clearInterval(progressInterval);
        importProgress.style.display = 'none';
        importStatus.style.display = 'block';
        importStatus.innerHTML = `
            <div class="error">
                ❌ Ошибка: ${error.message}
            </div>
        `;
        showNotification(`❌ Ошибка: ${error.message}`, 'error');
    }
};

// --- Импорт с почты (тестовый) ---
importEmailBtn.addEventListener('click', async () => {
    if (!token) {
        alert('Пожалуйста, войдите в систему');
        return;
    }
    try {
        await apiRequest('/import-from-email', 'POST');
        await Promise.all([loadSubscriptions(), loadAnalytics(), loadAIAdvice(), loadCategories()]);
        alert('Импорт выполнен (добавлены случайные подписки)');
    } catch (error) {
        alert(error.message);
    }
});

// --- Загрузка всех данных ---
async function loadAllData() {
    if (!token) return;
    await Promise.all([
        loadCategories(),
        loadUserSettings(),
        loadSubscriptions(),
        loadAnalytics(),
        loadAIAdvice()
    ]);
}

// --- Аутентификация ---
function updateUIForAuth() {
    if (token) {
        loginForm.style.display = 'none';
        userInfo.style.display = 'flex';
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            userEmailSpan.textContent = payload.sub;
        } catch {
            userEmailSpan.textContent = 'Пользователь';
        }
        appMain.style.display = 'block';
        loadAllData();
    } else {
        loginForm.style.display = 'flex';
        userInfo.style.display = 'none';
        appMain.style.display = 'none';
    }
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    try {
        const data = await apiRequest('/login', 'POST', { email, password });
        token = data.access_token;
        localStorage.setItem('token', token);
        updateUIForAuth();
    } catch (error) {
        alert('Ошибка входа: ' + error.message);
    }
});

document.getElementById('register-btn').addEventListener('click', async () => {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    if (!email || !password) {
        alert('Введите email и пароль');
        return;
    }
    try {
        const data = await apiRequest('/register', 'POST', { email, password });
        token = data.access_token;
        localStorage.setItem('token', token);
        updateUIForAuth();
    } catch (error) {
        alert('Ошибка регистрации: ' + error.message);
    }
});

logoutBtn.addEventListener('click', () => {
    localStorage.removeItem('token');
    token = null;
    updateUIForAuth();
});

// --- Закрытие модалок ---
[subClose, categoryClose].forEach(btn => {
    btn.addEventListener('click', () => {
        subModal.style.display = 'none';
        categoryModal.style.display = 'none';
    });
});

window.addEventListener('click', (e) => {
    if (e.target === subModal) subModal.style.display = 'none';
    if (e.target === categoryModal) categoryModal.style.display = 'none';
});

// --- Инициализация ---
updateUIForAuth();
apiRequest('/check-notifications', 'POST').catch(console.error);

// Периодическая проверка новых подписок
setInterval(() => {
    if (token) {
        loadSubscriptions();
        loadAnalytics();
    }
}, 30000);
