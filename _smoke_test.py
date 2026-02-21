from aksara import fields
from enum import Enum
from datetime import datetime

t = fields.Text(max_length=280)
print(f'Text(max_length=280): sql_type={t.sql_type}, max_length={t.max_length}')

f = fields.Float()
print(f'Float(): sql_type={f.sql_type}')

d = fields.Date()
print(f'Date(): sql_type={d.sql_type}')

dt = fields.DateTime(unique=True)
print(f'DateTime(unique=True): unique={dt.unique}')

b = fields.Boolean(unique=True)
print(f'Boolean(unique=True): unique={b.unique}')

class Status(Enum):
    DRAFT = 'draft'
e = fields.Enum(Status, unique=True)
print(f'Enum(unique=True): unique={e.unique}')

dec = fields.Decimal()
try:
    dec.validate('NaN')
    print('ERROR')
except ValueError:
    print('Decimal NaN blocked: OK')

try:
    dec.validate('Infinity')
    print('ERROR')
except ValueError:
    print('Decimal Infinity blocked: OK')

t2 = fields.Text(max_length=280)
t2.to_db('hello')
try:
    t2.to_db('x' * 281)
    print('ERROR')
except ValueError:
    print('Text max_length enforced: OK')

parsed = fields.DateTime().to_python('2024-01-15T10:30:00')
print(f'DateTime string parse: {type(parsed).__name__}')

s = fields.String(db_index=True)
print(f'String db_index={s.db_index}')

print('All checks passed!')
