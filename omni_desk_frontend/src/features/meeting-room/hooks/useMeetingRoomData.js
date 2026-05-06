import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import meetingRoomApi from '../api/meetingRoomApi';
import { handleError } from '../../../shared/api/responseHandler';

export const useMeetingRooms = () => {
  return useQuery({
    queryKey: ['meetingRooms'],
    queryFn: async () => {
      const response = await meetingRoomApi.getMeetingRooms();
      return response.data.results || [];
    },
    staleTime: 5 * 60 * 1000,
  });
};

export const useMeetingRoomBookings = () => {
  return useQuery({
    queryKey: ['meetingRoomBookings'],
    queryFn: async () => {
      const response = await meetingRoomApi.getMeetingRoomBookings();
      const bookingsData = response.data.results || [];
      return bookingsData.map((booking) => ({
        ...booking,
        start: new Date(booking.start_time),
        end: new Date(booking.end_time),
      }));
    },
    staleTime: 30 * 1000,
  });
};

export const useCreateMeetingRoomBooking = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => meetingRoomApi.createMeetingRoomBooking(data),
    onSuccess: () => {
      message.success('预约创建成功！');
      queryClient.invalidateQueries({ queryKey: ['meetingRoomBookings'] });
    },
    onError: (error) => {
      handleError(error, false);
    },
  });
};

export const useUpdateMeetingRoomBooking = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => meetingRoomApi.updateMeetingRoomBooking(id, data),
    onSuccess: () => {
      message.success('预约更新成功！');
      queryClient.invalidateQueries({ queryKey: ['meetingRoomBookings'] });
    },
    onError: (error) => {
      handleError(error, false);
    },
  });
};

export const useDeleteMeetingRoomBooking = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => meetingRoomApi.deleteMeetingRoomBooking(id),
    onSuccess: () => {
      message.success('预约删除成功！');
      queryClient.invalidateQueries({ queryKey: ['meetingRoomBookings'] });
    },
    onError: () => {
      message.error('删除预约失败。');
    },
  });
};
