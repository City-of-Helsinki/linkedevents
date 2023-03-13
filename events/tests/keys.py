from jose import jwk
from jose.constants import ALGORITHMS


def _build_key(private_pem, public_pem):
    class _Key:
        pass

    key = _Key()
    key.jose_algorithm = ALGORITHMS.RS256
    key.private_key_pem = private_pem
    key.public_key_pem = public_pem
    key.public_key_jwk = jwk.construct(public_pem, key.jose_algorithm).to_dict()

    # Ensure values are strings and not bytes
    for name in ["n", "e"]:
        value = key.public_key_jwk[name]
        if isinstance(value, bytes):
            key.public_key_jwk[name] = value.decode("utf-8")

    return key


rsa_key = _build_key(
    """-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDUeT3OFPatye6I
tmArvjR+f0lZu4QEOxtGxHj1UWzLiUbONygTrWCVXh5OFaH+GFPOfqax2iJSWc+7
6JYy2y2XxdG1Tehcvpsv/gKqRJG2afVKY+qCCmtRwksWan4kRU6F9UKDHJl6emkE
e9xA/+DRVAE7cCM1xblI7YD3zXsf1xIWHjYfLS6/EJeVnq/bCN84LPuCO6148N2D
H7E0PEH2oZyg0QlnU2tTcZMG2D172wFxyM8jGfy7Hm8X+MQH5N/aFeKb7f/6eTA7
4a5hW5ncRTasaH5djCcBFSyAaS8F4UCZYsRdth1lp4nBi986DbL1uaVbumU2Oo6F
a/K3uGRFAgMBAAECggEAAc5J/S9mbVGzCkxqgtSqA403ZWDXnWWXNMHEuWkIwK4Z
APWtDIXDtWFIZqd+afdw9udSqV5OPl7vCgzPAf2k5I5U2vKfj/I6xWymPyY4CtHZ
uNkijBpkkRxSoQ0kp1BDe5X7C7w5fbX+oIAg/hhuo7jQDd5FHlbg3ULPfsurSTj5
wnaekK64DgTM6N/kLbFKMbRmyC54EfBqu/H3fnY3uljNZGFnL0ueyGB0NEij/f7P
NXPzvi+r3Bmpe+K2P8mFBPNXhRIIUmfhxe19OcnkneGF3FTv+EqwzKid45/eSnC2
a8SeH/1b9pMPg0WycNwIh4sz3K7w0/vwJVpMC3thgQKBgQDq5pImHasJCIEHw2bY
A9NTGNP72ry8t96A6yLEa9w2i9lS7SMeUwuA5QdTE80+3FgC/S5YVxTyp0ceiUfr
nELEFgqD+6wXao6CYaelcwligmockXrBDGWfC/QviMRh6zympCZC0MNQcGR61PMx
tv8SqKi5ual+nT7PKqpbVygP5QKBgQDnjviEJa/E22VPoDZwnuwQCBf4fgQcOqSq
j2SYBLdISPzNhkXJqqlQ7LKZsWQH+4YeDDL2gOnmyvvQiRXlhQSNiCE26RSv1E3f
HiCvo8+AiDY49ywbbkL8E7sp5dSjmQhmQuRPolPMh2fJXvENxfEIXbwqpsCxxw0n
F3NGlpn84QKBgAtvCbIdQ5P++/jaxAjDtueWj8r0jLdK4+O2jkytS1zEVeG5dTom
pKqzezXKAvWKWCZdGIJoSra8+bM8z2lig8VzpTNjbq79Gs6x3i0pek13N58IXcdD
yTaCqHIf4B88Cgm6d7pM2xTxQ5LPBr9mvuezmfLgXKWzFbmTxBMKHQMZAoGATb33
e853U71hJzmf7XG9yagd/CS61otty4G3AT7cFh3DGnGRLqLok63UTLt83R06Kw5n
cdFYNk9B+gJ8YoGlRKtGk3vvoRTDTDx+Ntnlib6xjbCWk2MShDVPqkJqgL6ZTlP4
+S+DuPBhDP+eKMSjJu7phNxVZ5pvtQcvgayAaKECgYAsUa2jEZpLYwh2x+OW58YT
6Po5IhRvBAiNJg/N7mirkdb7NyB6I4aA1ztoimizDrJPn7edVKUTluNw2Fk3QsLS
va0XlEJu3URaqHLcKi6J74dlSt+3W4pSTJF7eseyFMI64bWSEho1tvChLSCq6lUE
zyIWjEHazLOEdBArFsgWsg==
-----END PRIVATE KEY-----""",
    """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1Hk9zhT2rcnuiLZgK740
fn9JWbuEBDsbRsR49VFsy4lGzjcoE61glV4eThWh/hhTzn6msdoiUlnPu+iWMtst
l8XRtU3oXL6bL/4CqkSRtmn1SmPqggprUcJLFmp+JEVOhfVCgxyZenppBHvcQP/g
0VQBO3AjNcW5SO2A9817H9cSFh42Hy0uvxCXlZ6v2wjfOCz7gjutePDdgx+xNDxB
9qGcoNEJZ1NrU3GTBtg9e9sBccjPIxn8ux5vF/jEB+Tf2hXim+3/+nkwO+GuYVuZ
3EU2rGh+XYwnARUsgGkvBeFAmWLEXbYdZaeJwYvfOg2y9bmlW7plNjqOhWvyt7hk
RQIDAQAB
-----END PUBLIC KEY-----""",
)
