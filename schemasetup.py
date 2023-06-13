def create_tables_and_indexes(cursor):
    cursor.execute("""
  create table if not exists corpus(
      filename varchar,
      sha256 varchar,
      label varchar,
      when_added datetime default current_timestamp,
      last_update datetime default current_timestamp
)
    """)
    cursor.execute("""create index if not exists
    corpus_filename on corpus(filename)""")
    cursor.execute("""create index if not exists
    corpus_sha256 on corpus(sha256)""")
    cursor.execute("""create index if not exists
    corpus_label on corpus(label)""")

    cursor.execute("""create table if not exists vectorisers (
     vectoriser_id integer primary key,
     vectoriser_pickle blob,
     when_added datetime default current_timestamp
     )""")

    cursor.execute("""
  create table if not exists model_pickles (
      model_id integer primary key,
      vectoriser integer references vectorisers(vectoriser_id),
      labelname varchar,
      model_pickle blob,
      when_added datetime default current_timestamp
  )""")

    cursor.execute("""
       create index if not exists model_pickles_by_name_and_time
            on model_pickles(labelname, when_added)""")
