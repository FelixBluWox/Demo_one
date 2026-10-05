from sqlalchemy import MetaData, Table, Column, Integer, String, insert, select, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from openpyxl import Workbook, load_workbook
from utils import Wox_log, error_form
from alive_progress import alive_bar
from colorama import Fore
import codecs, json, base64

wdb_log = Wox_log('database', color=Fore.LIGHTGREEN_EX)

metadata_obj = MetaData()

class Base(DeclarativeBase):
    pass

class Products(Base):
    __tablename__ = "products"

    iid: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str]
    name: Mapped[str]
    price: Mapped[int]
    stock: Mapped[int]
    upc: Mapped[int]
    thumb: Mapped[str]

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"



class Database():
    def __init__(self) -> None:
        wdb_log.info(f'iniciando base de datos')
        self.engine = create_engine("sqlite+pysqlite:///data/database.db", echo=True)
        self.session = Session(self.engine)
    
    def scal(self, stmt):
        return self.session.scalars(stmt)
    
    def get(self, id):
        self.session.get(Products, id)
    
    def ex(self, exp):
        with self.engine.connect() as conn:
            result = conn.execute(text(exp))
            conn.commit()






if __name__ == '__main__':
    #db = Database()
    #db.create_from_excel()
    pass