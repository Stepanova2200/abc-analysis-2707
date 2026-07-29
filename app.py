import pandas as pd
import numpy as np
import streamlit as st
import io


# Настройка страницы
st.set_page_config(
    page_title="📊 Анализ ассортимента",
    layout="wide"
)

st.title("ABC-анализ ассортимента")

# 🔎 Функция загрузки данных
@st.cache_data(ttl=600)
def load_data():
    """Загружает данные из BI_2807.xlsx."""
    
    # Путь к файлу можно изменить здесь
    file_path = "BI_2807.xlsx"

    try:
        df = pd.read_excel(file_path, sheet_name='Слияние1')
        
        required_cols = [
            'Предмет', 
            'Артикул поставщика',
            'Размер',
            'Склад',
            'продажи шт',
            'продажи руб',
            'Валовая прибыль, руб',
            'Маржинальность'
        ]
        
        missing = [col for col in required_cols if col not in df.columns]
        if len(missing) > 0:
            st.error(f"❌ Не найдены обязательные колонки {missing}")
            return None

        str_columns = ['Предмет', 'Артикул поставщика', 'Размер', 'Склад']
        for col in str_columns:
            df[col] = df[col].astype(str).str.strip()

        numeric_columns = ['продажи шт', 'продажи руб', 'Валовая прибыль, руб']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col])

        df.dropna(subset=['продажи шт'], inplace=True)

        return df

    except Exception as e:
        st.error(f"❌ Произошла ошибка при чтении файла:\n{e}")
        return None

# ⚙️ Основной блок приложения
data = load_data()
if data is None:
    st.stop()  

with st.sidebar.expander("Фильтр"):
    selected_subject = st.selectbox(
        label="Категория товара", options=["Все"] + list(data["Предмет"].unique()),
        index=0,
        help="Выбор категории."
    )

    selected_size = st.multiselect(
        label="Размер", options=data["Размер"].unique(), default=None,
        help="Оставить все — чтобы увидеть весь размерный ряд."
    )

    selected_warehouse = st.multiselect(
        label="Склад", options=data["Склад"].unique(), default=None,
        help="Выберите склад(ы) для анализа."
    )

filtered_data = data.copy()
if selected_subject != "Все":
    filtered_data = filtered_data.query('Предмет == @selected_subject')
if selected_size:
    filtered_data = filtered_data.query('@selected_size in Размер')
if selected_warehouse:
    filtered_data = filtered_data.query('@selected_warehouse in Склад')

aggregated = (
    filtered_data.groupby(['Предмет', 'Артикул поставщика'], as_index=False)
    .agg({
        'продажи шт': 'sum',
        'продажи руб': 'sum',
        'Валовая прибыль, руб': 'sum',
        'Маржинальность': 'mean'  # Среднее значение маржи по артикулу
    })
)

# KPI
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    units_sold = int(aggregated['продажи шт'].sum())
    st.metric(label="Количество продаж", value=f"{units_sold:,.0f}".replace(",", "\u202F"))

with kpi_col2:
    revenue = int(aggregated['продажи руб'].sum())
    st.metric(label="Выручка", value=f"{revenue:,.0f} ₽".replace(",", "\u202F"))

with kpi_col3:
    margin = int(aggregated['Валовая прибыль, руб'].sum())
    st.metric(label="Валовая прибыль", value=f"{margin:,.0f} ₽".replace(",", "\u202F"))

with kpi_col4:
    avg_margin_pct = round((aggregated['Валовая прибыль, руб'].sum() / aggregated['продажи руб'].sum()) * 100, 2)
    st.metric(label="Средняя маржа", value=f"{avg_margin_pct}%")

# Выбор критериев для ABC
st.write("---")  
st.subheader("Параметры ABC-анализа")

criteria_choice = st.radio(
    label="Критерий:",
    options=[
        ("Продажи, шт.", "продажи шт"),
        ("Выручка, ₽", "продажи руб"),
        ("Прибыль, ₽", "Валовая прибыль, руб"),
        ("Маржа, %", "Маржинальность")
    ],
    format_func=lambda x: x[0],
    horizontal=True,
)[1]

# ✍️ Сам ABC-анализ (встроен в основной файл)
def abc_analysis(df, column):
    """
    Проводит ABC-анализ по заданному столбцу.
    Возвращает DataFrame с категорией ABC.
    """
    sorted_df = df.sort_values(by=column, ascending=False)

    # Считаем кумулятивную сумму (нарастающий итог)
    sorted_df[f'Cumulative_{column}'] = sorted_df[column].cumsum()

    total_sum = sorted_df[column].sum()

    sorted_df['Cumulative_Percentage'] = (sorted_df[f'Cumulative_{column}'] / total_sum) * 100

    def assign_category(row):
        if row['Cumulative_Percentage'] <= 80:
            return 'A'
        elif row['Cumulative_Percentage'] <= 95:
            return 'B'
        else:
            return 'C'

    sorted_df['ABC_Category'] = sorted_df.apply(assign_category, axis=1)

    # Оставляем нужные колонки и добавляем порядковый номер для удобства
    result = sorted_df[
        ["Предмет", "Артикул поставщика", criteria_choice, f"Cumulative_{column}", "Cumulative_Percentage", "ABC_Category"]
    ].reset_index(drop=True)

    # Добавляем красивый индекс (от 1 до N)
    result.insert(0, "#", range(1, len(result) + 1))

    return result

result = abc_analysis(aggregated, criteria_choice)

# Таблица результатов
st.write("---")
st.subheader("Результаты ABC-анализа")

# Форматирование чисел через column_config
config = {
    criteria_choice: st.column_config.NumberColumn(format="%{value:,.0f}" + ("%" if "%" in criteria_choice else "")),
    f"Cumulative_{criteria_choice}": st.column_config.NumberColumn(format="%{value:,.0f}" + ("%" if "%" in criteria_choice else "")),
    "Cumulative_Percentage": st.column_config.ProgressColumn(format="%{value:.2f}%"),
}

st.dataframe(result, use_container_width=True, hide_index=True, column_config=config)

# 💾 Экспорт результатов в Excel (исправленная версия для pandas < 2.0)
with io.BytesIO() as buffer:
    # Записываем DataFrame в буфер
    result.to_excel(buffer, index=False)
    
    # Сбрасываем указатель на начало файла
    buffer.seek(0)
    
    # Передаём байты кнопки download_button
    st.download_button(
        label="Скачать результаты в Excel",
        data=buffer.read(),                     # <-- Здесь передаются байты
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_name=f"ABC-анализ ({criteria_choice}).xlsx"
    )