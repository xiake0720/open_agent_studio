from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    SQLAlchemy ORM 基类。

    所有数据库模型都继承 Base。
    后续执行 Base.metadata.create_all 时，会根据所有已导入的模型创建表。
    """
    pass