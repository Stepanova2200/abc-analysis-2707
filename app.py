import pandas as pd
import numpy as np
import streamlit as st
import io


# Настройка страницы
st.set_page_config(
    page_title="📊 Анализ ассортимента",
    layout="wide"
)

def load_data(uploaded_file=None):
    """
    Загружает данные либо из локального файла,
    либо из файла, который пользователь выбрал в браузере.
    """
    
    # Если пользователь загрузил файл напрямую в браузер
    if uploaded_file is not None:
        try:
            df = pd.read_excel(
                uploaded_file,
                sheet_name="Слияние1",  
                engine="openpyxl"      
            )
            
            st.success("Файл успешно загружен!")
        
        except Exception as e:
            st.error(f"Произошла ошибка при чтении файла:\n{e}")
            return None
    
    else:
        # Если файл не был загружен, используем стандартный пример
        file_path = "BI_2807.xlsx"
        
        try:
            df = pd.read_excel(file_path, sheet_name="Слияние1")
        
        except FileNotFoundError:
            st.warning("Локальный файл BI_2807.xlsx не найден.")
            st.info("Вы можете загрузить любой другой файл Excel ниже ↓")
            return None
    
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
        st.error(f"❌ Не найдены обязательные колонки {missing}. Пожалуйста, проверьте структуру вашего файла.")
        return None

    str_columns = ['Предмет', 'Артикул поставщика', 'Размер', 'Склад']
    for col in str_columns:
        df[col] = df[col].astype(str).str.strip()

    numeric_columns = ['продажи шт', 'продажи руб', 'Валовая прибыль, руб']
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col])

    df.dropna(subset=['продажи шт'], inplace=True)

    return df


def abc_dashboard(data):
    """Вкладка с ABC-анализом"""

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
    )[1]  # Берём второе значение кортежа (название реальной колонки)

    def abc_analysis(df, column):
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

        result = sorted_df[
            ["Предмет", "Артикул поставщика", column, f"Cumulative_{column}", "Cumulative_Percentage", "ABC_Category"]
        ].reset_index(drop=True)

        # 🔴️ ИСПРАВЛЕНИЕ ЗДЕСЬ: используем критерии_choice вместо локальной column
        config = {
            criteria_choice: st.column_config.NumberColumn(format="%{value:,.0f}" + ("%" if "%" in criteria_choice else "")),
            f"Cumulative_{criteria_choice}": st.column_config.NumberColumn(format="%{value:,.0f}" + ("%" if "%" in criteria_choice else "")),
            "Cumulative_Percentage": st.column_config.ProgressColumn(format="%{value:.2f}%"),
        }

        return result

    result = abc_analysis(aggregated, criteria_choice)

    # Таблица результатов
    st.write("---")
    st.subheader("Результаты ABC-анализа")

    st.dataframe(result, use_container_width=True, hide_index=True, column_config=config)

    # Экспорт результатов в Excel
    with io.BytesIO() as buffer:
        result.to_excel(buffer, index=False)
        buffer.seek(0)
        st.download_button(
            label="Скачать результаты в Excel",
            data=buffer.read(),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_name=f"ABC-анализ ({criteria_choice}).xlsx"
        )


def category_summary(data):
    """Вкладка со сводной таблицей по категориям"""

    # Агрегация данных по предмету (категории)
    pivot = (
        data.groupby(['Предмет'])
        .agg({
            'продажи шт': 'sum',
            # Агрегируем суммы с округлением до 2х знаков
            'продажи руб': lambda x: round(x.sum(), 2),
            'Валовая прибыль, руб': lambda x: round(x.sum(), 2)
        })
        .reset_index()
    )

    # Расчёт дополнительных метрик
    pivot['Маржа, %'] = round((pivot['Валовая прибыль, руб'] / pivot['продажи руб']) * 100, 2)

    # Сортируем строго по Марже в убывающем порядке
    pivot.sort_values(by='Маржа, %', ascending=False, inplace=True)

    # Форматирование чисел через column_config
    config = {
        'продажи руб': st.column_config.NumberColumn(format="%{value:,.2f} ₽"),
        'Валовая прибыль, руб': st.column_config.NumberColumn(format="%{value:,.2f} ₽"),
        'Маржа, %': st.column_config.ProgressColumn(format="%{value:.2f}%", min_value=0, max_value=100)
    }

    # Выводим результаты
    st.title("Сводная таблица по категориям:")
    st.dataframe(pivot, use_container_width=True, hide_index=True, column_config=config)


# ⚙️ Основной блок приложения
uploaded_file = st.file_uploader(
    label="Загрузите файл Excel с данными",
    type=["xlsx"],
    help="Поддерживается только формат .xlsx.",
    key="file_uploader"
)

if uploaded_file is not None or True:  # Проверяем наличие файла или дефолтного набора данных
    data = load_data(uploaded_file)
else:
    st.warning("Пожалуйста, загрузите корректный файл Excel.")
    st.stop()

# Меню навигации
page = st.sidebar.selectbox(
    "Навигация",
    ["ABC-анализ", "Сводная таблица категорий"],
    index=0,
    help="Переключайтесь между разными видами аналитики."
)

if page == "ABC-анализ":
    abc_dashboard(data)
elif page == "Сводная таблица категорий":
    category_summary(data)