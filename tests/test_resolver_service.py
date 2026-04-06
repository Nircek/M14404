from M14404.resolver_service import _normalize_host, _resolve_subdomain_key


def test_normalize_host() -> None:
    assert _normalize_host("abc.xyz") == "abc.xyz"
    assert _normalize_host("abc.xyz:8000") == "abc.xyz"
    assert _normalize_host("  www.ABC.xyz:443  ") == "www.abc.xyz"
    assert _normalize_host("") == ""


def test_resolve_subdomain_key() -> None:
    # Root domain
    assert _resolve_subdomain_key(host="abc.xyz", origin_domain_name="abc.xyz") == "_"
    assert (
        _resolve_subdomain_key(host="abc.xyz:8000", origin_domain_name="abc.xyz") == "_"
    )

    # www domain
    assert (
        _resolve_subdomain_key(host="www.abc.xyz", origin_domain_name="abc.xyz")
        == "www"
    )

    # Specific subdomains
    assert (
        _resolve_subdomain_key(host="about.abc.xyz", origin_domain_name="abc.xyz")
        == "about"
    )
    assert (
        _resolve_subdomain_key(host="blog.abc.xyz", origin_domain_name="abc.xyz")
        == "blog"
    )

    # Malicious/Confusing domains
    assert (
        _resolve_subdomain_key(host="fakeabc.xyz", origin_domain_name="abc.xyz") is None
    )
    assert (
        _resolve_subdomain_key(host="abc.xyz.com", origin_domain_name="abc.xyz") is None
    )
    assert (
        _resolve_subdomain_key(host="www_abc.xyz", origin_domain_name="abc.xyz") is None
    )

    # Empty inputs
    assert _resolve_subdomain_key(host="", origin_domain_name="abc.xyz") is None
    assert _resolve_subdomain_key(host="abc.xyz", origin_domain_name="") is None
