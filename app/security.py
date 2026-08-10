"""Controle de acesso aos painéis internos.

O formulário de pedido é público de propósito: quem está numa sala de reunião
precisa pedir café sem credencial. O painel da copa e o administrativo, não —
cada um exige uma senha definida por variável de ambiente.

Não existe cadastro de usuários. Isso é deliberado: o portal tem dois perfis
operacionais e nenhuma necessidade de identidade individual. Se um dia a trilha
de auditoria precisar dizer *quem* concluiu um pedido, e não apenas *qual perfil*,
esta é a camada a substituir por autenticação real.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from functools import wraps
from urllib.parse import urlparse

from flask import current_app, flash, redirect, request, session, url_for

ROLE_ADMIN = "admin"
ROLE_COPA = "copa"
SESSION_ROLES_KEY = "roles"

# Quem administra o portal também opera a copa.
ROLE_GRANTS: dict[str, set[str]] = {
    ROLE_ADMIN: {ROLE_ADMIN, ROLE_COPA},
    ROLE_COPA: {ROLE_COPA},
}

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "Administração",
    ROLE_COPA: "Copa",
}

PASSWORD_CONFIG_KEYS: dict[str, str] = {
    ROLE_ADMIN: "ADMIN_PASSWORD",
    ROLE_COPA: "COPA_PASSWORD",
}


def configured_password(role: str) -> str:
    """Senha configurada para o perfil, ou string vazia se não houver."""

    return current_app.config.get(PASSWORD_CONFIG_KEYS[role], "") or ""


def check_password(role: str, candidate: str) -> bool:
    """Compara a senha em tempo constante. Perfil sem senha nunca autentica."""

    expected = configured_password(role)
    if not expected:
        return False
    return hmac.compare_digest(expected, candidate or "")


def authenticate(candidate: str) -> str | None:
    """Descobre a qual perfil a senha informada corresponde.

    Administração é testada primeiro para que a senha mais poderosa vença em
    caso de configuração duplicada. As duas comparações são sempre executadas,
    para não vazar por tempo de resposta qual perfil existe.
    """

    matched_admin = check_password(ROLE_ADMIN, candidate)
    matched_copa = check_password(ROLE_COPA, candidate)

    if matched_admin:
        return ROLE_ADMIN
    if matched_copa:
        return ROLE_COPA
    return None


def grant_role(role: str) -> None:
    session[SESSION_ROLES_KEY] = sorted(ROLE_GRANTS[role])
    session.permanent = True


def revoke_roles() -> None:
    session.pop(SESSION_ROLES_KEY, None)


def current_roles() -> set[str]:
    stored = session.get(SESSION_ROLES_KEY) or []
    return {role for role in stored if role in ROLE_GRANTS}


def has_role(role: str) -> bool:
    return role in current_roles()


def is_authenticated() -> bool:
    return bool(current_roles())


def safe_redirect_target(candidate: str | None) -> str | None:
    """Só aceita destinos internos, para não virar um redirecionador aberto."""

    if not candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None

    return candidate


def login_required(role: str) -> Callable:
    """Exige o perfil informado; redireciona para o login preservando o destino."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            if has_role(role):
                return view(*args, **kwargs)

            if request.path.startswith("/api/") or request.is_json:
                return {"success": False, "message": "Acesso não autorizado."}, 401

            flash("Entre com a senha para acessar esta área.", "error")
            return redirect(url_for("main.login", next=request.full_path.rstrip("?")))

        return wrapped

    return decorator
