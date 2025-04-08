o
    ;��g�  �                   @   s�   U d dl mZmZ d dlmZ eejej�Z eed< dd� Zdd� Z	dd	� Z
d
d� Zdd� Zdd� Zdd� Zdd� Zdd� Zdd� Zdd� ZdS )�    )�create_client�Client)�Config�supabasec                 C   �   t �d��| ��� S )N�datphong�r   �table�insert�execute��data� r   �9C:\Users\Minh\Documents\GitHub\doan2\utils\db_supabase.py�insert_booking   �   r   c                 C   s"   t �d��d|d���d| ��� S )NZhoadonu   đã thanh toán)�	trangthaiZmagiaodichpaypalZmahoadon)r   r	   �update�eqr   )Z
ma_hoa_donZtransaction_idr   r   r   �update_payment_status	   s   
��r   c                   C   s   t �d��d��� S )N�phong�*)r   r	   �selectr   r   r   r   r   �	get_rooms   r   r   c                 C   r   )N�	khachhangr   r   r   r   r   �insert_user   r   r   c                 C   s   t �d��d��d| ��� S )Nr   r   �sodienthoai)r   r	   r   r   r   )�phoner   r   r   �get_user_by_phone   s   r   c                 C   s&   t �d��d��d| ��� �� }|jS )Nr   r   �email)r   r	   r   r   �singler   r   )r   �resr   r   r   �get_user_by_email   s    r"   c                 C   s    t �d��d��d| ��� �� S )Nr   r   �makhachhang�r   r	   r   r   r    r   )Zcustomer_idr   r   r   �get_customer_by_id   s    r%   c                 C   s(   t �d��d��d| ��d|��� �� S )Nr   r   r   �cccdr$   )r   r&   r   r   r   �get_user_by_credentials   s   �r'   c               
   C   s\   zt �d��d��dd��� } | jW S  ty- } ztd|� �� g W  Y d }~S d }~ww )Nr   r   r   �   Trốngu#   Lỗi khi lấy danh sách phòng: )r   r	   r   r   r   r   �	Exception�print)�response�er   r   r   �get_available_rooms$   s   ��r-   c              
   C   s�   z,t �d��d��d| ��� �� }td|� |jr&d|jv r&t|jd �W S t	d| � ��� t
yF } zdd l}|��  td|� � d }~ww )Nr   Ztongtien�
madatphongu    Kết quả truy vấn Supabase:u%   Không tìm thấy booking với ID: r   u   Lỗi khi truy vấn Supabase:)r   r	   r   r   r    r   r*   r   �float�
ValueErrorr)   �	traceback�	print_exc)�
booking_idr+   r,   r1   r   r   r   �get_booking_amount,   s    

��r4   c            	      C   s�   zPt �d��d��dd��� } | j}|sW dS d}|D ].}|�dd�}|�d	d
�}d�|�dd��}|�dd
�}|d|� d|� d|� d|� d�	7 }q|d7 }|W S  tyj } zdt	|�� d�W  Y d }~S d }~ww )Nr   r   r   r(   u-   <p>⚠️ Không có phòng trống nào.</p>uS  
        <table border="1" cellpadding="8" cellspacing="0">
            <thead>
                <tr>
                    <th>Mã phòng</th>
                    <th>Loại phòng</th>
                    <th>Giá (VNĐ)</th>
                    <th>Trạng thái</th>
                </tr>
            </thead>
            <tbody>
        �maphongzN/AZ	loaiphongu
   Không rõu
   {:,.0f}₫Zgiaphongr   z.
                <tr>
                    <td>z</td>
                    <td>z(</td>
                </tr>
            z</tbody></table>u2   <p>❌ Lỗi khi lấy danh sách phòng trống: z</p>)
r   r	   r   r   r   r   �get�formatr)   �str)	r+   Zdanh_sach_phong�htmlr   Zma_phongZ
loai_phongZgiaZ
trang_thair,   r   r   r   �#hien_thi_danh_sach_phong_trong_html=   s4   ������r:   N)r   r   r   �configr   ZSUPABASE_URLZSUPABASE_ANON_KEY�__annotations__r   r   r   r   r   r"   r%   r'   r-   r4   r:   r   r   r   r   �<module>   s    