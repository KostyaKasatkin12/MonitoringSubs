import os
import random
import smtplib
import imaplib
import email
import re
import logging
import json
import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone  # <-- ВАЖНО: добавлен timezone
from typing import List, Optional, Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from passlib.context import CryptContext
from jose import JWTError, jwt
import uvicorn
from contextlib import asynccontextmanager

# ---------- Настройки ----------
SECRET_KEY = "supersecretkeyforjwt123!"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# OpenRouter API ключ
OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Настройки SMTP Gmail
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "ks.kasatkin@gmail.com"
SMTP_PASSWORD = "zvmkqddcebitximh"
FROM_EMAIL = SMTP_USERNAME
FROM_NAME = "Константин Касаткин"

# База данных
SQLALCHEMY_DATABASE_URL = "sqlite:///./subscriptions.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Хеширование паролей
# Замените настройку pwd_context:
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256", "bcrypt"],  # pbkdf2_sha256 как основной
    deprecated="auto",
    pbkdf2_sha256__rounds=260000,  # Хороший уровень безопасности
    bcrypt__rounds=12
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# В начале файла добавьте словарь для категоризации сервисов
SERVICE_CATEGORIES = {
    # 🎬 Видео сервисы
    'netflix': '🎬 Видео',
    'netflix premium': '🎬 Видео',
    'ivi': '🎬 Видео',
    'okko': '🎬 Видео',
    'wink': '🎬 Видео',
    'kinopoisk': '🎬 Видео',
    'кинопоиск': '🎬 Видео',
    'youtube': '🎬 Видео',
    'youtube premium': '🎬 Виデオ',
    'twitch': '🎬 Видео',

    # 🎵 Музыка
    'spotify': '🎵 Музыка',
    'apple music': '🎵 Музыка',
    'yandex music': '🎵 Музыка',
    'яндекс музыка': '🎵 Музыка',
    'deezer': '🎵 Музыка',
    'soundcloud': '🎵 Музыка',

    # 🤖 AI сервисы
    'claude': '🤖 ИИ',
    'chatgpt': '🤖 ИИ',
    'openai': '🤖 ИИ',
    'midjourney': '🤖 ИИ',
    'copilot': '🤖 ИИ',

    # 🎨 Дизайн и творчество
    'photoshop': '🎨 Дизайн',
    'adobe': '🎨 Дизайн',
    'figma': '🎨 Дизайн',
    'canva': '🎨 Дизайн',
    'procreate': '🎨 Дизайн',

    # ☁️ Облачные сервисы
    'icloud': '☁️ Облако',
    'google drive': '☁️ Облако',
    'dropbox': '☁️ Облако',
    'yandex disk': '☁️ Облако',
    'яндекс диск': '☁️ Облако',
    'mega': '☁️ Облако',

    # 💻 Работа и продуктивность
    'notion': '💼 Работа',
    'slack': '💼 Работа',
    'zoom': '💼 Работа',
    'microsoft 365': '💼 Работа',
    'office 365': '💼 Работа',

    # 🛒 Покупки и доставка
    'ozon': '🛒 Покупки',
    'wildberries': '🛒 Покупки',
    'wb': '🛒 Покупки',
    'market': '🛒 Покупки',
    'яндекс маркет': '🛒 Покупки',

    # 🚗 Транспорт
    'yandex taxi': '🚗 Транспорт',
    'яндекс такси': '🚗 Транспорт',
    'uber': '🚗 Транспорт',
    'citymobil': '🚗 Транспорт',

    # 📚 Книги и образование
    'bookmate': '📚 Книги',
    'litres': '📚 Книги',
    'skillbox': '📚 Образование',
    'geekbrains': '📚 Образование',
    'stepik': '📚 Образование',

    # 🏋️ Спорт и здоровье
    'strava': '🏋️ Спорт',
    'fitness': '🏋️ Спорт',
    'health': '🏋️ Спорт',

    # 🎮 Игры
    'steam': '🎮 Игры',
    'playstation': '🎮 Игры',
    'xbox': '🎮 Игры',
    'nintendo': '🎮 Игры',
    'epic games': '🎮 Игры',

    # 📱 Сервисы Apple
    'apple': '📱 Apple',
    'app store': '📱 Apple',

    # 💳 Банки и финансы
    'tinkoff': '💳 Банки',
    'сбер': '💳 Банки',
    'sber': '💳 Банки',
    'alfa': '💳 Банки',
    'raiffeisen': '💳 Банки',
}

# Цвета для категорий
CATEGORY_COLORS = {
    '🎬 Видео': '#FF2D55',  # Ярко-розовый как в Apple TV
    '🎵 Музыка': '#FF9500',  # Оранжевый как в Apple Music
    '🤖 ИИ': '#5856D6',  # Фиолетовый
    '🎨 Дизайн': '#FF3B30',  # Красный
    '☁️ Облако': '#5AC8FA',  # Голубой
    '💼 Работа': '#4CD964',  # Зеленый
    '🛒 Покупки': '#FFCC00',  # Желтый
    '🚗 Транспорт': '#007AFF',  # Синий
    '📚 Книги': '#AF52DE',  # Пурпурный
    '📚 Образование': '#FF6482',  # Розовый
    '🏋️ Спорт': '#30B0C0',  # Бирюзовый
    '🎮 Игры': '#FF375F',  # Ярко-розовый
    '📱 Apple': '#A2A2A2',  # Серый
    '💳 Банки': '#00A86B',  # Изумрудный
}


# ---------- Модели SQLAlchemy ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    notification_enabled = Column(Boolean, default=True)
    five_minute_notifications = Column(Boolean, default=True)

    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, default="#3498db")
    is_test = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint('user_id', 'name', name='unique_category_per_user'),)

    user = relationship("User", back_populates="categories")
    subscriptions = relationship("Subscription", back_populates="category_rel")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String, default="RUB")
    period = Column(String, nullable=False)
    next_payment = Column(DateTime, nullable=False)
    auto_renewal = Column(Boolean, default=True)
    last_notification_sent = Column(DateTime, nullable=True)
    five_minute_notification_sent = Column(Boolean, default=False)
    imported_from = Column(String, nullable=True)

    user = relationship("User", back_populates="subscriptions")
    category_rel = relationship("Category", back_populates="subscriptions")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.now(timezone.utc))
    type = Column(String)
    message = Column(String)

    user = relationship("User", back_populates="notifications")
    subscription = relationship("Subscription")


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    analysis_text = Column(String, nullable=False)
    recommendations = Column(String, nullable=True)

    user = relationship("User", back_populates="ai_analyses")


User.ai_analyses = relationship("AIAnalysis", back_populates="user", cascade="all, delete-orphan")

# Создаём таблицы
Base.metadata.create_all(bind=engine)


# ---------- Pydantic схемы ----------
class UserCreate(BaseModel):
    email: str
    password: str  # Убедитесь, что здесь нет никаких валидаторов

    # Если есть model_config, убедитесь, что он не изменяет данные
    model_config = ConfigDict(extra='forbid')


class UserOut(BaseModel):
    id: int
    email: str
    notification_enabled: bool
    five_minute_notifications: bool


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class CategoryBase(BaseModel):
    name: str
    color: str = "#3498db"
    is_test: bool = False


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int
    user_id: int
    subscription_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class SubscriptionBase(BaseModel):
    category_id: int
    name: str
    price: float
    currency: str = "RUB"
    period: str
    next_payment: datetime
    auto_renewal: bool = True


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(SubscriptionBase):
    pass


class SubscriptionOut(SubscriptionBase):
    id: int
    user_id: int
    category_name: str
    category_color: str
    category_is_test: bool
    imported_from: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AnalyticsOut(BaseModel):
    total_monthly: float
    by_category: dict
    upcoming: List[dict]
    urgent: List[dict]


class AIAdvice(BaseModel):
    advice: str


class AIAnalysisOut(BaseModel):
    id: int
    created_at: datetime
    analysis_text: str
    recommendations: Optional[List[str]] = None


class NotificationOut(BaseModel):
    id: int
    subscription_name: str
    sent_at: datetime
    type: str
    message: str


class UserSettings(BaseModel):
    notification_enabled: bool
    five_minute_notifications: bool


class ImportProgress(BaseModel):
    processed: int
    total: int
    found: int


# ---------- Вспомогательные функции ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password, hashed_password):
    """Проверка пароля с обрезкой до 72 символов"""
    # Преобразуем в строку, если это байты
    if isinstance(plain_password, bytes):
        plain_password = plain_password.decode('utf-8')

    # Обрезаем до 72 символов
    if len(plain_password) > 72:
        plain_password = plain_password[:72]

    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Хеширование пароля с обрезкой до 72 символов"""
    try:
        logger.info(f"get_password_hash input type: {type(password)}, value: {password}")

        # Преобразуем в строку, если это байты
        if isinstance(password, bytes):
            password = password.decode('utf-8')
            logger.info(f"Decoded bytes to string: {password}")

        # Проверяем длину в байтах (важно для bcrypt!)
        password_bytes = password.encode('utf-8')
        logger.info(f"Password length in bytes: {len(password_bytes)}")

        # Обрезаем до 72 байт, если нужно
        if len(password_bytes) > 72:
            logger.warning(f"Password too long ({len(password_bytes)} bytes), truncating to 72 bytes")
            password = password[:72]
            password_bytes = password.encode('utf-8')

        # Хешируем строку
        result = pwd_context.hash(password)
        logger.info(f"Password hashed successfully, hash length: {len(result)}")
        return result

    except Exception as e:
        logger.error(f"Error in get_password_hash: {e}")
        logger.error(f"Password type: {type(password)}, value: {password}")
        raise


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Увеличим время жизни токена для отладки
        expire = datetime.now(timezone.utc) + timedelta(days=7)  # 7 дней вместо 24 часов
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Token created for {data.get('sub')}, expires at {expire}")
    return encoded_jwt


from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Получение текущего пользователя из токена"""
    if not token:
        logger.warning("No token provided")
        return None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Декодируем токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")

        if email is None:
            logger.warning("Token has no email subject")
            raise credentials_exception

        token_data = TokenData(email=email)

        # Проверяем срок действия токена
        exp = payload.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            if exp_datetime < datetime.now(timezone.utc):
                logger.warning(f"Token expired for {email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    except jwt.ExpiredSignatureError:
        logger.warning("Token signature expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError as e:
        logger.warning(f"JWT Error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        raise credentials_exception

    # Ищем пользователя в базе данных
    user = db.query(User).filter(User.email == token_data.email).first()

    if user is None:
        logger.warning(f"User not found: {token_data.email}")
        raise credentials_exception

    logger.info(f"User authenticated: {user.email}")
    return user


# ---------- Функции для уведомлений ----------
async def send_email_notification(to_email: str, subject: str, body: str):
    """Отправка email через Gmail"""
    try:
        print("\n" + "=" * 60)
        print(f"📧 ОТ: {FROM_NAME} <{FROM_EMAIL}>")
        print(f"📧 КОМУ: {to_email}")
        print(f"📋 ТЕМА: {subject}")
        print(f"📄 ТЕКСТ:\n{body}")
        print("=" * 60 + "\n")

        msg = MIMEMultipart()
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"✅ Письмо отправлено от {FROM_NAME} на {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Ошибка авторизации Gmail: {e}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")
        return True


async def check_and_send_notifications():
    """Проверка подписок и отправка уведомлений"""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # 1. Проверка на 5 минут
        five_minute_subs = db.query(Subscription).filter(
            Subscription.next_payment <= now + timedelta(minutes=5),
            Subscription.next_payment > now,
            Subscription.auto_renewal == True,
            Subscription.five_minute_notification_sent == False
        ).all()

        print(f"\n⏰ Найдено {len(five_minute_subs)} подписок, которые спишутся через 5 минут")

        for sub in five_minute_subs:
            user = sub.user
            if not user or not user.notification_enabled or not user.five_minute_notifications:
                continue

            minutes_left = int((sub.next_payment - now).total_seconds() / 60)

            subject = f"🚨 СРОЧНО! Через {minutes_left} мин. спишется {sub.name}"
            body = f"""
⚠️ СРОЧНОЕ УВЕДОМЛЕНИЕ!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Подписка:    {sub.name}
Категория:   {sub.category_rel.name}
Сумма:       {sub.price} {sub.currency}
Дата:        {sub.next_payment.strftime('%d.%m.%Y %H:%M')}
Осталось:    {minutes_left} минут
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Проверьте наличие средств на карте, чтобы избежать проблем с оплатой.

С уважением,
{FROM_NAME}
            """

            success = await send_email_notification(user.email, subject, body)

            if success:
                sub.five_minute_notification_sent = True
                notification = Notification(
                    user_id=user.id,
                    subscription_id=sub.id,
                    type="five_minute",
                    message=f"Уведомление за 5 минут: {sub.name} - {sub.price} {sub.currency}"
                )
                db.add(notification)
                db.commit()
                print(f"✅ Отправлено срочное уведомление для {sub.name}")

        # 2. Проверка на 3 дня
        upcoming_subs = db.query(Subscription).filter(
            Subscription.next_payment <= now + timedelta(days=3),
            Subscription.next_payment > now,
            Subscription.auto_renewal == True
        ).all()

        print(f"📋 Найдено {len(upcoming_subs)} подписок с предстоящими платежами (3 дня)")

        for sub in upcoming_subs:
            if sub.last_notification_sent and (now - sub.last_notification_sent).days < 1:
                continue

            user = sub.user
            if not user or not user.notification_enabled:
                continue

            days_left = (sub.next_payment - now).days + 1
            subject = f"⚠️ Напоминание: {sub.name} - списание через {days_left} дн."
            body = f"""
Здравствуйте!

Напоминаю о предстоящем списании по подписке:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Подписка:    {sub.name}
Категория:   {sub.category_rel.name}
Сумма:       {sub.price} {sub.currency}
Дата:        {sub.next_payment.strftime('%d.%m.%Y %H:%M')}
Осталось:    {days_left} дн.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Это автоматическое уведомление от вашего помощника по подпискам.

С уважением,
{FROM_NAME}
            """

            success = await send_email_notification(user.email, subject, body)

            if success:
                sub.last_notification_sent = now
                notification = Notification(
                    user_id=user.id,
                    subscription_id=sub.id,
                    type="upcoming",
                    message=f"Уведомление о списании {sub.name} через {days_left} дн."
                )
                db.add(notification)
                db.commit()
                print(f"✅ Уведомление обработано для подписки {sub.name}")

        return {
            "message": f"Проверка завершена. 5-минутных: {len(five_minute_subs)}, 3-дневных: {len(upcoming_subs)}"
        }
    except Exception as e:
        print(f"❌ Ошибка при проверке уведомлений: {e}")
        return {"error": str(e)}
    finally:
        db.close()


async def send_test_notification(subscription: Subscription, user: User, db: Session):
    """Отправка тестового уведомления"""
    subject = f"🧪 ТЕСТ: {subscription.name}"
    body = f"""
ТЕСТОВОЕ УВЕДОМЛЕНИЕ

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Категория:   {subscription.category_rel.name} (ТЕСТОВАЯ)
Подписка:    {subscription.name}
Сумма:       {subscription.price} {subscription.currency}
Период:      {subscription.period}
Дата:        {subscription.next_payment.strftime('%d.%m.%Y %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Это тестовое уведомление для проверки работы системы.

С уважением,
{FROM_NAME}
    """

    success = await send_email_notification(user.email, subject, body)

    if success:
        notification = Notification(
            user_id=user.id,
            subscription_id=subscription.id,
            type="test",
            message=f"Тестовое уведомление для {subscription.name}"
        )
        db.add(notification)
        db.commit()

    return success


# ---------- Функции для AI анализа ----------
async def get_ai_analysis(user_id: int, db: Session) -> List[str]:
    """Получение AI анализа через OpenRouter"""
    try:
        subs = db.query(Subscription).filter(Subscription.user_id == user_id).all()

        if not subs:
            return ["У вас пока нет подписок. Добавьте первую подписку для получения анализа!"]

        subscriptions_data = []
        total_monthly = 0

        for s in subs:
            if s.period == "год":
                monthly = s.price / 12
            else:
                monthly = s.price
            total_monthly += monthly

            minutes_to = int((s.next_payment - datetime.now(timezone.utc)).total_seconds() / 60)

            subscriptions_data.append({
                "name": s.name,
                "category": s.category_rel.name if s.category_rel else "Без категории",
                "price": s.price,
                "monthly_price": round(monthly, 2),
                "currency": s.currency,
                "period": s.period,
                "next_payment_minutes": minutes_to,
                "auto_renewal": s.auto_renewal
            })

        prompt = f"""
        Проанализируй мои подписки. Общая сумма в месяц: {round(total_monthly, 2)} RUB.

        Мои подписки:
        {json.dumps(subscriptions_data, ensure_ascii=False, indent=2)}

        Дай 3-5 конкретных советов по оптимизации расходов на русском языке.
        Обрати особое внимание на подписки, которые скоро спишутся (менее 5 минут).
        Каждый совет должен быть отдельной строкой.
        Формат ответа: просто список советов, каждый с новой строки.
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Subscription Monitor"
        }

        data = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [
                {"role": "system",
                 "content": "Ты эксперт по управлению личными финансами и подписками. Даешь конкретные, практические советы."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=data, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_response = result['choices'][0]['message']['content']

                    advice_list = [line.strip() for line in ai_response.split('\n') if line.strip()]

                    ai_analysis = AIAnalysis(
                        user_id=user_id,
                        analysis_text=ai_response,
                        recommendations=json.dumps(advice_list, ensure_ascii=False)
                    )
                    db.add(ai_analysis)
                    db.commit()

                    logger.info(f"✅ AI анализ получен для пользователя {user_id}: {len(advice_list)} советов")
                    return advice_list
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка OpenRouter API: {response.status} - {error_text}")
                    return get_fallback_advice(subs)

    except Exception as e:
        logger.error(f"❌ Ошибка при получении AI анализа: {e}")
        return get_fallback_advice(subs if 'subs' in locals() else [])


def get_fallback_advice(subs: List[Subscription]) -> List[str]:
    """Запасные советы если AI недоступен"""
    advices = []

    total_monthly = 0
    expensive_subs = []
    upcoming = []
    urgent = []

    now = datetime.now(timezone.utc)

    for s in subs:
        if s.period == "год":
            monthly = s.price / 12
        else:
            monthly = s.price
        total_monthly += monthly

        if s.price > 1000:
            expensive_subs.append(s.name)

        minutes_to = int((s.next_payment - now).total_seconds() / 60)

        if 0 <= minutes_to <= 5:
            urgent.append(s.name)
        elif 0 <= minutes_to <= 4320:  # 3 дня в минутах
            upcoming.append(s.name)

    if urgent:
        advices.append(f"🚨 СРОЧНО! Через {minutes_to} минут спишутся: {', '.join(urgent)}. Проверьте баланс!")

    if expensive_subs:
        advices.append(f"⚠️ Дорогие подписки (>1000): {', '.join(expensive_subs)}. Подумайте о смене тарифа.")

    if upcoming:
        advices.append(f"⏰ Скоро списание (3 дня): {', '.join(upcoming)}. Проверьте баланс.")

    if total_monthly > 5000:
        advices.append(f"💰 Общие расходы {total_monthly:.0f} руб/мес. Это много! Пересмотрите подписки.")

    if not advices:
        advices.append("✅ У вас оптимальный набор подписок. Так держать!")

    return advices


# ---------- Класс для парсинга email ----------
class EmailSubscriptionParser:
    """Универсальный парсер подписок из email с AI анализом"""

    PROVIDERS = {
        'gmail': {
            'imap': 'imap.gmail.com',
            'port': 993,
            'ssl': True,
            'name': 'Gmail',
            'folders': ['INBOX', '[Gmail]/All Mail']
        },
        'yandex': {
            'imap': 'imap.yandex.ru',
            'port': 993,
            'ssl': True,
            'name': 'Яндекс',
            'folders': ['INBOX', 'Входящие']
        },
        'mailru': {
            'imap': 'imap.mail.ru',
            'port': 993,
            'ssl': True,
            'name': 'Mail.ru',
            'folders': ['INBOX']
        }
    }

    def __init__(self, email_address: str, password: str):
        self.email = email_address
        self.password = password
        self.provider = self._detect_provider(email_address)
        self.imap = None
        self.processed_count = 0
        self.found_count = 0

    def _detect_provider(self, email: str) -> str:
        email_lower = email.lower()
        if 'gmail.com' in email_lower:
            return 'gmail'
        elif 'yandex' in email_lower or 'ya.ru' in email_lower:
            return 'yandex'
        elif 'mail.ru' in email_lower or 'inbox.ru' in email_lower:
            return 'mailru'
        else:
            return 'gmail'

    async def connect(self) -> bool:
        try:
            config = self.PROVIDERS[self.provider]
            self.imap = imaplib.IMAP4_SSL(config['imap'], config['port'])
            self.imap.login(self.email, self.password)
            logger.info(f"✅ Подключено к {config['name']}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            return False

    def disconnect(self):
        if self.imap:
            try:
                self.imap.logout()
            except:
                self.imap.close()

    def _decode_str(self, text) -> str:
        if isinstance(text, bytes):
            try:
                return text.decode('utf-8', errors='ignore')
            except:
                return text.decode('latin-1', errors='ignore')
        return str(text)

    def _get_email_body(self, msg) -> str:
        body = ""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += self._decode_str(payload)
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = self._decode_str(payload)
        except Exception as e:
            logger.error(f"Ошибка извлечения тела письма: {e}")
        return body

    async def extract_subscription_info_with_ai(self, subject: str, body: str, from_addr: str) -> Optional[Dict]:
        """Упрощенный парсер подписок из писем"""
        try:
            logger.info(f"📧 Анализ письма: {subject[:100]}")
            logger.info(f"✉️ От: {from_addr}")

            # Проверяем ключевые слова в теме и теле
            text_to_check = (subject + " " + body[:500]).lower()

            # Слова-маркеры подписок
            subscription_keywords = [
                'подписка', 'subscription', 'оплата', 'payment', 'списание',
                'renewal', 'продление', 'invoice', 'счет', 'receipt', 'чек'
            ]

            is_subscription = any(keyword in text_to_check for keyword in subscription_keywords)

            if not is_subscription:
                logger.info(f"❌ Не похоже на подписку: {subject}")
                return None

            logger.info(f"✅ Похоже на подписку: {subject}")

            # Пытаемся найти название сервиса
            name = None

            # Из отправителя
            if '@' in from_addr:
                # Пробуем извлечь домен
                domain = from_addr.split('@')[1].split('.')[0].lower()
                if domain in ['netflix', 'spotify', 'apple', 'google', 'yandex', 'mail', 'youtube']:
                    name = domain.capitalize()

            # Из темы
            common_services = {
                'netflix': 'Netflix', 'spotify': 'Spotify', 'apple': 'Apple',
                'google': 'Google', 'yandex': 'Яндекс', 'mail.ru': 'Mail.ru',
                'youtube': 'YouTube', 'amazon': 'Amazon', 'paypal': 'PayPal',
                'adobe': 'Adobe', 'microsoft': 'Microsoft', 'notion': 'Notion'
            }

            for service, full_name in common_services.items():
                if service in text_to_check:
                    name = full_name
                    break

            if not name:
                name = "Неизвестный сервис"

            # Пытаемся найти цену
            price = None
            price_patterns = [
                r'(\d+[\.,]?\d*)\s*₽',
                r'(\d+[\.,]?\d*)\s*руб',
                r'(\d+[\.,]?\d*)\s*\$',
                r'(\d+[\.,]?\d*)\s*USD',
                r'(\d+[\.,]?\d*)\s*EUR',
                r'price:?\s*(\d+[\.,]?\d*)',
                r'sum:?\s*(\d+[\.,]?\d*)'
            ]

            for pattern in price_patterns:
                match = re.search(pattern, body[:1000], re.IGNORECASE)
                if match:
                    price = float(match.group(1).replace(',', '.'))
                    break

            # Определяем валюту
            currency = "RUB"
            if 'usd' in text_to_check or '$' in text_to_check:
                currency = "USD"
            elif 'eur' in text_to_check or '€' in text_to_check:
                currency = "EUR"

            # Определяем период
            period = "месяц"
            if 'год' in text_to_check or 'year' in text_to_check or 'annual' in text_to_check:
                period = "год"

            result = {
                'name': name,
                'price': price if price else 0,
                'currency': currency,
                'period': period,
                'next_payment': None
            }

            logger.info(f"✅ Извлечено: {result}")
            return result

        except Exception as e:
            logger.error(f"Ошибка анализа письма: {e}")
            return None

    async def search_subscriptions(self, days_back: int = 180) -> List[Dict]:
        if not self.imap and not await self.connect():
            return []

        subscriptions = []
        self.processed_count = 0
        self.found_count = 0

        try:
            self.imap.select('INBOX')

            since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            search_criteria = f'(SINCE "{since_date}")'

            typ, message_ids = self.imap.search(None, 'ALL', search_criteria)

            if typ != 'OK' or not message_ids[0]:
                logger.warning("Нет писем для анализа")
                return []

            total = len(message_ids[0].split())
            logger.info(f"📧 Найдено писем: {total}")

            for idx, msg_id in enumerate(message_ids[0].split()):
                self.processed_count += 1
                logger.info(f"📨 Обработка письма {idx + 1}/{total}")

                try:
                    typ, msg_data = self.imap.fetch(msg_id, '(RFC822)')
                    msg = email.message_from_bytes(msg_data[0][1])

                    subject_header = msg.get('Subject', '')
                    subject_parts = decode_header(subject_header)
                    subject = ''
                    for part, encoding in subject_parts:
                        if isinstance(part, bytes):
                            subject += part.decode(encoding if encoding else 'utf-8', errors='ignore')
                        else:
                            subject += part

                    from_header = msg.get('From', '')
                    body = self._get_email_body(msg)

                    logger.info(f"📧 Тема: {subject[:100]}")
                    logger.info(f"✉️ От: {from_header}")

                    sub_info = await self.extract_subscription_info_with_ai(subject, body, from_header)

                    if sub_info:
                        self.found_count += 1
                        sub_info['source_email'] = self.email
                        sub_info['source_provider'] = self.provider
                        subscriptions.append(sub_info)
                        logger.info(
                            f"✅ НАЙДЕНА ПОДПИСКА: {sub_info['name']} - {sub_info['price']} {sub_info['currency']}")
                    else:
                        logger.info(f"❌ Не найдено подписки в письме")

                except Exception as e:
                    logger.error(f"Ошибка обработки письма {idx + 1}: {e}")
                    continue

            logger.info(f"📊 ИТОГО: обработано {self.processed_count}, найдено {self.found_count} подписок")

        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
        finally:
            self.disconnect()

        return subscriptions

    def get_progress(self):
        return {
            'processed': self.processed_count,
            'found': self.found_count
        }


# ---------- Функции для импорта подписок ----------
async def process_email_import(creds: dict, db: Session):
    """Фоновая задача для импорта подписок с умной категоризацией"""

    # Используем session.get() вместо query.get()
    user = db.get(User, creds['user_id'])
    if not user:
        logger.error(f"User {creds['user_id']} not found")
        return

    added_subscriptions = []
    skipped_subscriptions = []
    categorized_counts = {}

    try:
        parser = EmailSubscriptionParser(creds['email'], creds['password'])
        subscriptions = await parser.search_subscriptions(days_back=180)

        # Группируем подписки по названию, оставляя самую свежую
        latest_subscriptions = {}

        for sub_info in subscriptions:
            name = sub_info.get('name', '')
            if not name:
                continue

            # Получаем дату следующего платежа
            next_payment = sub_info.get('next_payment')
            if isinstance(next_payment, str):
                try:
                    next_payment = datetime.fromisoformat(next_payment)
                    # Если дата без timezone, добавляем UTC
                    if next_payment.tzinfo is None:
                        next_payment = next_payment.replace(tzinfo=timezone.utc)
                except:
                    next_payment = datetime.now(timezone.utc) + timedelta(days=30)
            else:
                next_payment = datetime.now(timezone.utc) + timedelta(days=30)

            # Определяем категорию для подписки
            category_name = '📦 Другое'
            name_lower = name.lower()

            for key, cat in SERVICE_CATEGORIES.items():
                if key in name_lower:
                    category_name = cat
                    break

            # Сохраняем с категорией
            if name not in latest_subscriptions:
                latest_subscriptions[name] = {
                    'info': sub_info,
                    'next_payment': next_payment,
                    'category': category_name
                }
            else:
                existing_date = latest_subscriptions[name]['next_payment']
                if next_payment > existing_date:
                    latest_subscriptions[name] = {
                        'info': sub_info,
                        'next_payment': next_payment,
                        'category': category_name
                    }

        # Получаем все существующие подписки пользователя
        existing_subs = db.query(Subscription).filter(
            Subscription.user_id == user.id
        ).all()

        # Создаем или получаем категории
        category_objects = {}

        # Создаем все возможные категории
        all_categories = set(SERVICE_CATEGORIES.values()) | {'📦 Другое'}
        for cat_name in all_categories:
            category = db.query(Category).filter(
                Category.user_id == user.id,
                Category.name == cat_name
            ).first()

            if not category:
                color = CATEGORY_COLORS.get(cat_name, '#8E8E93')
                category = Category(
                    user_id=user.id,
                    name=cat_name,
                    color=color,
                    is_test=False
                )
                db.add(category)
                db.commit()
                db.refresh(category)

            category_objects[cat_name] = category

        # Сохраняем подписки
        saved_count = 0
        for name, data in latest_subscriptions.items():
            sub_info = data['info']
            next_payment = data['next_payment']
            category_name = data['category']
            category = category_objects[category_name]

            name_lower = name.lower()

            # Проверяем на дубликаты
            is_duplicate = False

            for existing in existing_subs:
                if name_lower in existing.name.lower():
                    price_diff = abs(existing.price - float(sub_info.get('price', 0)))
                    if price_diff < 1.0 or (existing.price > 0 and price_diff / existing.price < 0.1):
                        is_duplicate = True
                        existing.next_payment = next_payment
                        existing.category_id = category.id
                        db.add(existing)
                        skipped_subscriptions.append(f"{name} (обновлена)")
                        break

            if not is_duplicate:
                subscription = Subscription(
                    user_id=user.id,
                    category_id=category.id,
                    name=name,
                    price=float(sub_info.get('price', 0)),
                    currency=sub_info.get('currency', 'RUB'),
                    period=sub_info.get('period', 'месяц'),
                    next_payment=next_payment,
                    auto_renewal=True,
                    imported_from=f"email:{parser.provider}"
                )
                db.add(subscription)
                saved_count += 1
                added_subscriptions.append({
                    'name': name,
                    'price': sub_info.get('price', 0),
                    'currency': sub_info.get('currency', 'RUB'),
                    'category': category_name
                })

                if category_name not in categorized_counts:
                    categorized_counts[category_name] = 0
                categorized_counts[category_name] += 1

        db.commit()

        # Формируем красивый отчет
        result_message = "📱 **IMPORT COMPLETE**\n"
        result_message += "══════════════════════════════\n\n"

        result_message += f"✅ **+{saved_count} новых подписок**\n"
        if skipped_subscriptions:
            result_message += f"🔄 **{len(skipped_subscriptions)} обновлено**\n"
        result_message += "\n"

        if added_subscriptions:
            result_message += "**НОВЫЕ ПОДПИСКИ:**\n"
            for sub in added_subscriptions:
                icon = sub['category'].split()[0]
                result_message += f"{icon} • **{sub['name']}** — {sub['price']} {sub['currency']}\n"

        if categorized_counts:
            result_message += "\n**ПО КАТЕГОРИЯМ:**\n"
            for cat, count in categorized_counts.items():
                result_message += f"{cat} × {count}\n"

        result_message += "\n══════════════════════════════\n"
        result_message += "✨ Импорт выполнен успешно!"

        await send_email_notification(
            user.email,
            f"📱 Импорт подписок: +{saved_count}",
            result_message
        )

        logger.info(f"✅ Импорт завершен для {user.email}: +{saved_count} новых, {len(skipped_subscriptions)} обновлено")

    except Exception as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        logger.error(f"Error details:", exc_info=True)
        await send_email_notification(
            user.email,
            "❌ Ошибка импорта",
            f"Произошла ошибка: {str(e)}"
        )

# ---------- Инициализация FastAPI ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - запускаем периодическую проверку
    asyncio.create_task(periodic_notification_check())
    yield
    # Shutdown - здесь можно добавить код для завершения

# Инициализация FastAPI с lifespan
app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Раздача статики
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------- Эндпоинты ----------
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

@app.get("/verify-token")
async def verify_token(current_user: User = Depends(get_current_user)):
    """Проверка валидности токена"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email
    }

# Аутентификация
@app.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        logger.info(f"=== REGISTRATION ATTEMPT ===")
        logger.info(f"Email: {user.email}")
        logger.info(f"Password length: {len(user.password)}")
        logger.info(f"Password bytes length: {len(user.password.encode('utf-8'))}")
        logger.info(f"Password value: '{user.password}'")

        # Проверка существования пользователя
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            logger.warning(f"User already exists: {user.email}")
            raise HTTPException(status_code=400, detail="Email already registered")

        # Проверка длины пароля (в символах, не в байтах!)
        if len(user.password) < 6:
            logger.warning(f"Password too short for {user.email}")
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        # Хеширование пароля
        logger.info(f"Hashing password for {user.email}")
        hashed = get_password_hash(user.password)

        # Создание пользователя
        new_user = User(email=user.email, hashed_password=hashed)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"User created with ID: {new_user.id}")

        # Создание категорий по умолчанию
        logger.info(f"Creating default categories for user {new_user.id}")
        default_category = Category(user_id=new_user.id, name="Развлечения", color="#9b59b6")
        db.add(default_category)

        test_category = Category(user_id=new_user.id, name="ТЕСТ(КРАСНАЯ)", color="#e74c3c", is_test=True)
        db.add(test_category)
        db.commit()
        logger.info(f"Categories created successfully")

        # Создание токена
        access_token = create_access_token(data={"sub": new_user.email})
        logger.info(f"Registration successful for {user.email}")

        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"REGISTRATION ERROR: {str(e)}")
        logger.error(f"Error details:", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(get_db)):
    authenticated_user = authenticate_user(db, user.email, user.password)
    if not authenticated_user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": authenticated_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# Эндпоинты для категорий
@app.get("/categories", response_model=List[CategoryOut])
def get_categories(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    categories = db.query(Category).filter(Category.user_id == current_user.id).all()
    result = []
    for cat in categories:
        cat_dict = {
            "id": cat.id,
            "name": cat.name,
            "color": cat.color,
            "is_test": cat.is_test,
            "user_id": cat.user_id,
            "subscription_count": len(cat.subscriptions)
        }
        result.append(cat_dict)
    return result


@app.post("/categories", response_model=CategoryOut)
def create_category(
        category: CategoryCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    existing = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name == category.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category with this name already exists")

    new_category = Category(**category.model_dump(), user_id=current_user.id)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    return {
        "id": new_category.id,
        "name": new_category.name,
        "color": new_category.color,
        "is_test": new_category.is_test,
        "user_id": new_category.user_id,
        "subscription_count": 0
    }


@app.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
        category_id: int,
        category_update: CategoryCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.name != category_update.name:
        existing = db.query(Category).filter(
            Category.user_id == current_user.id,
            Category.name == category_update.name
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Category with this name already exists")

    category.name = category_update.name
    category.color = category_update.color
    category.is_test = category_update.is_test
    db.commit()
    db.refresh(category)

    return {
        "id": category.id,
        "name": category.name,
        "color": category.color,
        "is_test": category.is_test,
        "user_id": category.user_id,
        "subscription_count": len(category.subscriptions)
    }


@app.delete("/categories/{category_id}")
def delete_category(
        category_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.subscriptions:
        raise HTTPException(status_code=400, detail="Cannot delete category with subscriptions")

    db.delete(category)
    db.commit()
    return {"ok": True}


# Эндпоинты для подписок
@app.get("/subscriptions", response_model=List[SubscriptionOut])
def get_subscriptions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    subs = db.query(Subscription).filter(Subscription.user_id == current_user.id).all()
    result = []
    for sub in subs:
        sub_dict = {
            "id": sub.id,
            "user_id": sub.user_id,
            "category_id": sub.category_id,
            "name": sub.name,
            "price": sub.price,
            "currency": sub.currency,
            "period": sub.period,
            "next_payment": sub.next_payment,
            "auto_renewal": sub.auto_renewal,
            "category_name": sub.category_rel.name if sub.category_rel else "Без категории",
            "category_color": sub.category_rel.color if sub.category_rel else "#95a5a6",
            "category_is_test": sub.category_rel.is_test if sub.category_rel else False,
            "imported_from": sub.imported_from
        }
        result.append(sub_dict)
    return result


@app.post("/subscriptions", response_model=SubscriptionOut)
def create_subscription(
        sub: SubscriptionCreate,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    category = db.query(Category).filter(
        Category.id == sub.category_id,
        Category.user_id == current_user.id
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    new_sub = Subscription(**sub.model_dump(), user_id=current_user.id)
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)

    if category.is_test:
        background_tasks.add_task(send_test_notification, new_sub, current_user, db)

    return {
        "id": new_sub.id,
        "user_id": new_sub.user_id,
        "category_id": new_sub.category_id,
        "name": new_sub.name,
        "price": new_sub.price,
        "currency": new_sub.currency,
        "period": new_sub.period,
        "next_payment": new_sub.next_payment,
        "auto_renewal": new_sub.auto_renewal,
        "category_name": category.name,
        "category_color": category.color,
        "category_is_test": category.is_test,
        "imported_from": None
    }


@app.put("/subscriptions/{sub_id}", response_model=SubscriptionOut)
def update_subscription(
        sub_id: int,
        sub_update: SubscriptionUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sub = db.query(Subscription).filter(
        Subscription.id == sub_id,
        Subscription.user_id == current_user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if sub_update.category_id != sub.category_id:
        category = db.query(Category).filter(
            Category.id == sub_update.category_id,
            Category.user_id == current_user.id
        ).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

    for key, value in sub_update.model_dump().items():
        setattr(sub, key, value)
    db.commit()
    db.refresh(sub)

    return {
        "id": sub.id,
        "user_id": sub.user_id,
        "category_id": sub.category_id,
        "name": sub.name,
        "price": sub.price,
        "currency": sub.currency,
        "period": sub.period,
        "next_payment": sub.next_payment,
        "auto_renewal": sub.auto_renewal,
        "category_name": sub.category_rel.name,
        "category_color": sub.category_rel.color,
        "category_is_test": sub.category_rel.is_test,
        "imported_from": sub.imported_from
    }


@app.delete("/subscriptions/{sub_id}")
def delete_subscription(
        sub_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sub = db.query(Subscription).filter(
        Subscription.id == sub_id,
        Subscription.user_id == current_user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.delete(sub)
    db.commit()
    return {"ok": True}


# Эндпоинты для импорта
# Эндпоинты для импорта подписок (исправленная версия)
@app.post("/import/email")
async def import_from_email(
        background_tasks: BackgroundTasks,
        request: dict,  # Принимаем как dict из body
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Импорт подписок из email
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    email = request.get('email')
    password = request.get('password')

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    temp_creds = {
        'email': email,
        'password': password,
        'user_id': current_user.id
    }

    background_tasks.add_task(process_email_import, temp_creds, db)

    return {
        "message": "Импорт начат. Это может занять несколько минут.",
        "status": "processing"
    }


@app.post("/import/gmail")
async def import_gmail(
        background_tasks: BackgroundTasks,
        request: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Импорт из Gmail"""
    return await import_from_email(background_tasks, request, current_user, db)


@app.post("/import/yandex")
async def import_yandex(
        background_tasks: BackgroundTasks,
        request: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Импорт из Яндекс.Почты"""
    return await import_from_email(background_tasks, request, current_user, db)


@app.post("/import/mailru")
async def import_mailru(
        background_tasks: BackgroundTasks,
        request: dict,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Импорт из Mail.ru"""
    return await import_from_email(background_tasks, request, current_user, db)


# Эндпоинт для AI анализа
@app.get("/ai-analysis", response_model=List[AIAdvice])
async def ai_analysis(
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    background_tasks.add_task(run_ai_analysis_background, current_user.id, db)

    last_analysis = db.query(AIAnalysis).filter(
        AIAnalysis.user_id == current_user.id
    ).order_by(AIAnalysis.created_at.desc()).first()

    if last_analysis and last_analysis.recommendations:
        try:
            recommendations = json.loads(last_analysis.recommendations)
            return [AIAdvice(advice=adv) for adv in recommendations]
        except:
            return [AIAdvice(advice=last_analysis.analysis_text)]

    subs = db.query(Subscription).filter(Subscription.user_id == current_user.id).all()
    fallback = get_fallback_advice(subs)
    return [AIAdvice(advice=adv) for adv in fallback]


async def run_ai_analysis_background(user_id: int, db: Session):
    advice = await get_ai_analysis(user_id, db)
    logger.info(f"AI анализ завершен для пользователя {user_id}")


# Эндпоинт для настроек пользователя
@app.get("/user/settings", response_model=UserSettings)
def get_user_settings(
        current_user: User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "notification_enabled": current_user.notification_enabled,
        "five_minute_notifications": current_user.five_minute_notifications
    }


@app.post("/user/settings", response_model=UserSettings)
def update_user_settings(
        settings: UserSettings,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    current_user.notification_enabled = settings.notification_enabled
    current_user.five_minute_notifications = settings.five_minute_notifications
    db.commit()

    return {
        "notification_enabled": current_user.notification_enabled,
        "five_minute_notifications": current_user.five_minute_notifications
    }


# Эндпоинт для уведомлений
@app.get("/notifications", response_model=List[NotificationOut])
def get_notifications(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.sent_at.desc()).limit(50).all()

    result = []
    for n in notifications:
        result.append({
            "id": n.id,
            "subscription_name": n.subscription.name if n.subscription else "Неизвестно",
            "sent_at": n.sent_at,
            "type": n.type,
            "message": n.message
        })
    return result


# Эндпоинт для тестовых уведомлений
@app.post("/test-notification/{subscription_id}")
async def test_notification(
        subscription_id: int,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sub = db.query(Subscription).filter(
        Subscription.id == subscription_id,
        Subscription.user_id == current_user.id
    ).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    background_tasks.add_task(send_test_notification, sub, current_user, db)

    return {"message": "Тестовое уведомление отправлено"}


# Аналитика
@app.get("/analytics", response_model=AnalyticsOut)
async def analytics(
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    subs = db.query(Subscription).filter(Subscription.user_id == current_user.id).all()
    total = 0.0
    by_cat = {}
    upcoming = []
    urgent = []

    now = datetime.now(timezone.utc)

    for s in subs:
        if s.period == "год":
            monthly = s.price / 12
        else:
            monthly = s.price
        total += monthly

        cat_name = s.category_rel.name if s.category_rel else "Без категории"
        by_cat[cat_name] = by_cat.get(cat_name, 0) + monthly

        minutes_until = int((s.next_payment - now).total_seconds() / 60)
        days_until = (s.next_payment.date() - now.date()).days

        if 0 <= minutes_until <= 5:
            urgent.append({
                "name": s.name,
                "amount": s.price,
                "currency": s.currency,
                "date": s.next_payment.isoformat(),
                "category": cat_name,
                "minutes_left": minutes_until
            })
        elif 0 <= days_until <= 7:
            upcoming.append({
                "name": s.name,
                "amount": s.price,
                "currency": s.currency,
                "date": s.next_payment.isoformat(),
                "category": cat_name,
                "days_left": days_until
            })

    background_tasks.add_task(run_ai_analysis_background, current_user.id, db)

    return {
        "total_monthly": round(total, 2),
        "by_category": by_cat,
        "upcoming": upcoming,
        "urgent": urgent
    }


# Фоновое задание для проверки уведомлений
@app.post("/check-notifications")
async def check_notifications():
    result = await check_and_send_notifications()
    return result


# Импорт с почты (тестовый)
@app.post("/import-from-email")
def import_from_email_old(
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    services = [
        {"name": "Netflix", "category": "Развлечения", "price": 999, "currency": "RUB", "period": "месяц"},
        {"name": "Spotify", "category": "Музыка", "price": 169, "currency": "RUB", "period": "месяц"},
        {"name": "Photoshop", "category": "Работа", "price": 799, "currency": "RUB", "period": "месяц"},
        {"name": "iCloud", "category": "Облако", "price": 99, "currency": "RUB", "period": "месяц"},
        {"name": "YouTube Premium", "category": "Развлечения", "price": 299, "currency": "RUB", "period": "месяц"}
    ]

    categories = {}
    for service in services:
        cat_name = service["category"]
        category = db.query(Category).filter(
            Category.user_id == current_user.id,
            Category.name == cat_name
        ).first()
        if not category:
            category = Category(user_id=current_user.id, name=cat_name)
            db.add(category)
            db.commit()
            db.refresh(category)
        categories[cat_name] = category

    count = random.randint(1, 2)
    selected = random.sample(services, count)
    created = []

    for s in selected:
        next_pay = datetime.now(timezone.utc) + timedelta(days=random.randint(1, 30))
        next_pay = next_pay.replace(hour=12, minute=0, second=0)
        sub = Subscription(
            user_id=current_user.id,
            category_id=categories[s["category"]].id,
            name=s["name"],
            price=s["price"],
            currency=s["currency"],
            period=s["period"],
            next_payment=next_pay,
            auto_renewal=True
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        created.append(sub)

        if categories[s["category"]].is_test:
            background_tasks.add_task(send_test_notification, sub, current_user, db)

    return {"imported": [{"name": c.name, "id": c.id} for c in created]}


async def periodic_notification_check():
    """Периодическая проверка уведомлений каждую минуту"""
    while True:
        await asyncio.sleep(60)
        try:
            await check_and_send_notifications()
        except Exception as e:
            logger.error(f"Ошибка в периодической проверке: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
