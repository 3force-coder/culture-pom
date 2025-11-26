# Users configuration with bcrypt hashed passwords
# ADMIN: admin_3force / Admin@2025
# USER: user_judumas / User@2025

USERS = {
    'admin_3force': {
        'name': 'Admin 3Force',
        'email': '3force@culturepom.com',
        'password_hash': '$2b$12$Bg38E/voHSrQ2Vk3atNR6eDbmQAckRwdJPSf8mBPyfX1gTOEQN59m',
        'role': 'ADMIN'
    },
    'user_judumas': {
        'name': 'Julien Dumas',
        'email': 'judumas10@gmail.com',
        'password_hash': '$2b$12$7nQ4v63pW2TyMxiriADBw.HhxWBySs6IhzJg7XaUh2bNdpoc2a4kO',
        'role': 'USER'
    },
    'compteur_inventaire': {
        'name': 'Compteur Inventaire',
        'email': 'compteur@culturepom.com',
        'password_hash': '$2b$12$KQX7jMnP9vR2wH5nYzEuXeF4L7GkM3pN8qQ5rS6tT9uU2vW0xX1yY2',
        'role': 'COMPTEUR'
    }
}
